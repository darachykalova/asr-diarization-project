from celery import Celery


celery_app = Celery(
    "asr_diarization_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1"
)

celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,
    timezone="Europe/Minsk",
    enable_utc=True
)