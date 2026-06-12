from pathlib import Path
from uuid import uuid4
from typing import Optional

from services.worker_job_service import WorkerJobService
from celery_app.app import celery_app


@celery_app.task(name="process_audio_task")
def process_audio_task(
    input_audio: str,
    normalized_audio: Optional[str] = None,
    output_json: Optional[str] = None,
    log_file: Optional[str] = None,
    model_size: str = "base",
    language: str | None = None,
    job_id: Optional[str] = None
) -> dict:
    """
    Celery task for processing one audio file.

    Task status is stored in Celery backend.
    The transcript result is still saved to transcript.json.
    """
    if job_id is None:
        job_id = f"job_{uuid4().hex}"

    job_output_dir = Path("data/output/jobs") / job_id
    normalized_dir = Path("data/normalized/jobs") / job_id

    if normalized_audio is None:
        normalized_audio = str(normalized_dir / "audio_16k_mono.wav")

    if output_json is None:
        output_json = str(job_output_dir / "transcript.json")

    if log_file is None:
        log_file = str(job_output_dir / "pipeline.log")

    worker_job_service = WorkerJobService(
        model_size=model_size,
        language=language,
        log_file=log_file
    )

    run_result = worker_job_service.run_job(
        input_audio=input_audio,
        normalized_audio=normalized_audio,
        output_json=output_json,
        job_id=job_id
    )

    return run_result.model_dump()