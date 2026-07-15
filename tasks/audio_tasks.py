import logging

from celery import chain as celery_chain
from celery.signals import worker_process_init, worker_ready
from celery_app.app import celery_app
from database import crud
from database.session import SessionLocal

logger = logging.getLogger(__name__)


def build_pipeline_chain(
    job_id: str,
    input_key: str,
    language: str | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
    whisper_model: str | None = None,
    initial_prompt: str | None = None,
    webhook_url: str | None = None,
):
    from tasks.pipeline_tasks import (
        normalize_task, asr_task, diarize_task,
        merge_align_task, persist_task,
        identify_speakers_task, finalize_task,
        chain_error_handler,
    )

    ctx = {
        "job_id": job_id,
        "input_key": input_key,
        "params": {
            "language": language,
            "min_speakers": min_speakers,
            "max_speakers": max_speakers,
            # None -> auto-select model from audio quality in asr_task;
            # a value -> explicit user override (skips quality check).
            "whisper_model": whisper_model,
            "initial_prompt": initial_prompt,
            "webhook_url": webhook_url,
        },
    }

    error_cb = chain_error_handler.s(job_id=job_id)

    return celery_chain(
        normalize_task.s(ctx),
        asr_task.s(),
        diarize_task.s(),
        merge_align_task.s(),
        persist_task.s(),
        identify_speakers_task.s(),
        finalize_task.s(),
    ).on_error(error_cb)


@worker_process_init.connect
def on_worker_process_init(**kwargs):
    import os
    logger.info("Prefork worker process PID=%s ready", os.getpid())


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Once per worker start (not per prefork child): requeue jobs orphaned
    by a previous worker/broker crash. See tasks/recovery.py."""
    from tasks.recovery import requeue_stuck_jobs

    db = SessionLocal()
    try:
        requeued = requeue_stuck_jobs(db)
        if requeued:
            logger.warning("startup self-heal: requeued %d stuck job(s): %s",
                           len(requeued), requeued)
    except Exception:
        logger.exception("startup self-heal failed — worker starting anyway")
    finally:
        db.close()


@celery_app.task(name="dead_letter_task", queue="dead_letter")
def dead_letter_task(job_id: str, error: str, original_kwargs: dict) -> None:
    logger.error("DLQ: job_id=%s error=%s", job_id, error)
    db = SessionLocal()
    try:
        crud.update_job_status(
            db=db,
            job_id=job_id,
            status="failed",
            error_code="MAX_RETRIES_EXCEEDED",
            error_message=error,
        )
    finally:
        db.close()
