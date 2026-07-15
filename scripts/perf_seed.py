"""
Заполнение БД синтетическими данными для нагрузочного тестирования.
Цель: ~50 000 jobs + transcripts; замер list/analytics/FTS.

Использование:
  docker compose exec api python scripts/perf_seed.py [--count 50000] [--bench]

Флаг --bench: не вставляет данные, только замеряет скорость на уже заполненной БД.
"""
import argparse
import os
import random
import sys
import time
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database.session import SessionLocal

_WORDS_RU = (
    "привет мир голос запись транскрипция аудио спикер диаризация"
    " обработка текст данные анализ система сервис клиент звонок"
    " встреча совещание разговор сотрудник менеджер директор план"
    " проект задача результат работа качество отчёт итог вопрос"
).split()

_STATUSES = ["done"] * 7 + ["failed"] * 1 + ["partial"] * 1 + ["processing"] * 1

_BATCH = 500


def _random_text(n_words: int = 80) -> str:
    return " ".join(random.choices(_WORDS_RU, k=n_words))


def _ts(days_ago: float) -> datetime:
    return datetime.utcnow() - timedelta(days=days_ago)


def seed(db, count: int) -> None:
    print(f"Вставка {count} jobs + transcripts батчами по {_BATCH}…")
    inserted = 0

    while inserted < count:
        batch_size = min(_BATCH, count - inserted)

        jobs_data = []
        transcripts_data = []

        for _ in range(batch_size):
            job_id = str(uuid.uuid4())
            status = random.choice(_STATUSES)
            created = _ts(random.uniform(0, 365))
            finished = created + timedelta(seconds=random.randint(30, 600)) if status in ("done", "failed", "partial") else None
            jobs_data.append({
                "id": job_id,
                "status": status,
                "audio_key": f"uploads/{job_id}.mp3",
                "params": '{"whisper_model": "base"}',
                "progress": 100 if status == "done" else random.randint(0, 99),
                "created_at": created,
                "finished_at": finished,
            })
            if status == "done":
                ft = _random_text(random.randint(40, 120))
                transcripts_data.append({
                    "job_id": job_id,
                    "status": "done",
                    "success": True,
                    "full_text": ft,
                    "duration_sec": random.uniform(30, 3600),
                    "created_at": created,
                })

        db.execute(
            text("""
                INSERT INTO jobs (id, status, audio_key, params, progress, created_at, finished_at)
                VALUES (:id, :status, :audio_key, :params::jsonb, :progress, :created_at, :finished_at)
                ON CONFLICT (id) DO NOTHING
            """),
            jobs_data,
        )

        if transcripts_data:
            db.execute(
                text("""
                    INSERT INTO transcripts (job_id, status, success, full_text,
                                            full_text_vector, duration_sec, created_at)
                    VALUES (:job_id, :status, :success, :full_text,
                            to_tsvector('simple', :full_text), :duration_sec, :created_at)
                    ON CONFLICT (job_id) DO NOTHING
                """),
                transcripts_data,
            )

        db.commit()
        inserted += batch_size
        print(f"  {inserted}/{count} вставлено…", end="\r")

    print(f"\nГотово: {inserted} jobs вставлено.")


def bench(db) -> None:
    print("\n--- Замер производительности ---")

    queries = [
        ("Список audio (page 1)", "SELECT id, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 20 OFFSET 0"),
        ("Список audio + filter status=done", "SELECT id, status, created_at FROM jobs WHERE status='done' ORDER BY created_at DESC LIMIT 20"),
        ("analytics summary", "SELECT status, count(*) FROM jobs GROUP BY status"),
        ("uploads_over_time (day)", "SELECT date_trunc('day', created_at) AS d, count(*) FROM jobs GROUP BY d ORDER BY d"),
        ("FTS поиск 'голос'", "SELECT t.job_id FROM transcripts t WHERE t.full_text_vector @@ plainto_tsquery('simple', 'голос') LIMIT 20"),
        ("frequent_words (ts_stat)", "SELECT word, ndoc FROM ts_stat('SELECT full_text_vector FROM transcripts WHERE full_text_vector IS NOT NULL') ORDER BY ndoc DESC LIMIT 50"),
    ]

    for label, sql in queries:
        t0 = time.perf_counter()
        rows = db.execute(text(sql)).fetchall()
        elapsed = time.perf_counter() - t0
        status = "OK" if elapsed < 3.0 else "SLOW"
        print(f"  [{status}] {label}: {elapsed:.3f}s ({len(rows)} rows)")

    print("\nКритерии (SC-005/SC-006): список/аналитика < 3 c, FTS < 2 c")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed performance test data")
    parser.add_argument("--count", type=int, default=50_000, help="Кол-во jobs (default: 50000)")
    parser.add_argument("--bench", action="store_true", help="Только замер, без вставки")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if not args.bench:
            seed(db, args.count)
        bench(db)
    finally:
        db.close()
