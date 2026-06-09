import os

from celery import Celery


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
    backend=REDIS_BACKEND_URL
)

celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,
    timezone="Europe/Minsk",
    enable_utc=True
)