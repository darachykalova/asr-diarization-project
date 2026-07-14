"""Тесты полнотекстового поиска по транскриптам (нужен запущенный postgres)."""
import uuid
from datetime import datetime

from sqlalchemy import text

from database import crud
from database.session import SessionLocal


def _insert_transcript(db, job_id: str, full_text: str) -> None:
    db.execute(text(
        "INSERT INTO jobs (id, status, progress, created_at) VALUES (:jid, 'done', 0, :now)"
    ), {"jid": job_id, "now": datetime.utcnow()})
    db.execute(text("""
        INSERT INTO transcripts (job_id, status, success, full_text,
                                 full_text_vector, language, duration_sec, created_at)
        VALUES (:jid, 'done', true, :ft, to_tsvector('simple', :ft), 'ru', 10.0, :now)
    """), {"jid": job_id, "ft": full_text, "now": datetime.utcnow()})
    db.commit()


def _cleanup(db, job_id: str) -> None:
    try:
        db.execute(text("DELETE FROM transcripts WHERE job_id = :jid"), {"jid": job_id})
        db.execute(text("DELETE FROM jobs WHERE id = :jid"), {"jid": job_id})
        db.commit()
    except Exception:
        db.rollback()


def test_search_finds_transcript_by_word():
    db = SessionLocal()
    jid = f"test-search-{uuid.uuid4().hex[:8]}"
    try:
        _insert_transcript(db, jid, "сегодня обсуждали квартальный отчёт по продажам")
        results = crud.search_transcripts_fulltext("отчёт", limit=10)
        found = [r for r in results if r["job_id"] == jid]
        assert len(found) == 1
        assert "отчёт" in found[0]["snippet"].lower()
        assert found[0]["language"] == "ru"
        assert isinstance(found[0]["created_at"], str)
    finally:
        _cleanup(db, jid)
        db.close()


def test_search_no_match_returns_empty():
    results = crud.search_transcripts_fulltext("абракадабрищенко")
    assert results == []
