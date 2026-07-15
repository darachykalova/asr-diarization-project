"""Self-healing: перезапуск pipeline-задач, осиротевших после падения worker'а/брокера.

Если worker или Redis умирают посреди обработки, задача исчезает из очереди,
а строка в jobs остаётся в processing/queued навсегда (acks_late не спасает,
когда потерян сам брокер). На старте worker'а requeue_stuck_jobs находит такие
строки и ставит конвейер заново — шаги идемпотентны (persist удаляет старый
транскрипт перед записью), поэтому повторный прогон безопасен.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

from sqlalchemy import and_, or_

from database.models import Job

logger = logging.getLogger(__name__)

DEFAULT_MAX_AGE_HOURS = float(os.getenv("STUCK_JOB_MAX_AGE_HOURS", "2"))


def _default_enqueue(job: Job) -> None:
    from tasks.audio_tasks import build_pipeline_chain

    params = job.params or {}
    build_pipeline_chain(
        job_id=job.id,
        input_key=job.audio_key,
        language=params.get("language"),
        min_speakers=params.get("min_speakers"),
        max_speakers=params.get("max_speakers"),
        whisper_model=params.get("whisper_model"),
        initial_prompt=params.get("initial_prompt"),
        webhook_url=params.get("webhook_url"),
    ).apply_async(task_id=job.id)


def requeue_stuck_jobs(db, enqueue=None,
                       max_age_hours: float = DEFAULT_MAX_AGE_HOURS) -> list[str]:
    """Перезапустить задания, застрявшие в processing/queued дольше max_age_hours.

    Возвращает список перезапущенных job_id. Задания без audio_key перезапустить
    нечем — помечаются failed, чтобы не висеть в UI вечной обработкой.
    """
    enqueue = enqueue or _default_enqueue
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    stuck = (
        db.query(Job)
        .filter(or_(
            and_(Job.status == "processing", Job.started_at < cutoff),
            and_(Job.status == "queued", Job.created_at < cutoff),
        ))
        .all()
    )
    requeued: list[str] = []
    for job in stuck:
        if not job.audio_key:
            logger.warning(
                "stuck job %s has no audio_key — cannot requeue, marking failed",
                job.id)
            job.status = "failed"
            job.error_code = "STUCK_NO_AUDIO"
            job.error_message = "job orphaned by worker crash; no audio_key to requeue"
            job.finished_at = datetime.utcnow()
            db.commit()
            continue
        # Сначала статус в БД, потом очередь: если enqueue упадёт, задание
        # останется старым queued и попадёт в следующий проход самолечения.
        job.status = "queued"
        job.progress = 0
        job.started_at = None
        db.commit()
        enqueue(job)
        requeued.append(job.id)
        logger.warning("requeued stuck job %s (audio_key=%s)", job.id, job.audio_key)
    return requeued
