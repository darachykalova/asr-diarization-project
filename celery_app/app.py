import os

from celery import Celery
from kombu import Queue


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0"
)

REDIS_BACKEND_URL = os.getenv(
    "REDIS_BACKEND_URL",
    "redis://localhost:6379/1"
)

celery_app = Celery(
    "asr_diarization_worker",
    broker=REDIS_URL,
    backend=REDIS_BACKEND_URL,
    include=["tasks.audio_tasks", "tasks.pipeline_tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,
    timezone="Europe/Minsk",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_queues=(
        Queue("default"),
        Queue("dead_letter"),
    ),
    task_default_queue="default",
    task_routes={
        "pipeline.normalize":              {"queue": "default"},
        "pipeline.asr":                    {"queue": "default"},
        "pipeline.diarize":                {"queue": "default"},
        "pipeline.merge_align":            {"queue": "default"},
        "pipeline.persist":                {"queue": "default"},
        "pipeline.identify_speakers":      {"queue": "default"},
        "pipeline.finalize":               {"queue": "default"},
        "pipeline.chain_error_handler":    {"queue": "default"},
    },
)