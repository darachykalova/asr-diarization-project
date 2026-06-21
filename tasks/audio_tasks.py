import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

from celery_app.app import celery_app
from clients.minio_client import MinioStorageClient
from database import crud
from database.session import SessionLocal
from services.webhook_service import send_webhook
from services.worker_job_service import WorkerJobService


def _update_job_status_safely(
    job_id: str,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None
) -> None:
    db = SessionLocal()

    try:
        crud.update_job_status(
            db=db,
            job_id=job_id,
            status=status,
            error_code=error_code,
            error_message=error_message
        )

    finally:
        db.close()


def _send_webhook_safely(
    webhook_url: str | None,
    job_id: str,
    status: str,
    error: str | None = None
) -> None:
    if not webhook_url:
        return

    payload = {
        "job_id": job_id,
        "status": status,
        "error": error
    }

    send_webhook(
        url=webhook_url,
        payload=payload
    )


def _download_audio_from_minio(
    object_key: str
) -> str:
    suffix = Path(object_key).suffix

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix
    )

    temp_file.close()

    storage_client = MinioStorageClient()

    storage_client.download_file(
        object_key=object_key,
        local_path=temp_file.name
    )

    return temp_file.name


def _delete_temp_file(
    file_path: str | None
) -> None:
    if not file_path:
        return

    try:
        Path(file_path).unlink(
            missing_ok=True
        )

    except Exception:
        pass


@celery_app.task(name="process_audio_task")
def process_audio_task(
    input_audio: str,
    normalized_audio: Optional[str] = None,
    output_json: Optional[str] = None,
    log_file: Optional[str] = None,
    model_size: str = "base",
    language: str | None = None,
    job_id: Optional[str] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    webhook_url: Optional[str] = None,
    initial_prompt: Optional[str] = None,
    input_storage: str = "local"
) -> dict:
    if job_id is None:
        job_id = f"job_{uuid4().hex}"

    downloaded_audio_path = None

    try:
        if input_storage == "minio":
            downloaded_audio_path = _download_audio_from_minio(
                input_audio
            )

            input_audio = downloaded_audio_path

        job_output_dir = Path("data/output/jobs") / job_id
        normalized_dir = Path("data/normalized/jobs") / job_id

        if normalized_audio is None:
            normalized_audio = str(
                normalized_dir / "audio_16k_mono.wav"
            )

        if output_json is None:
            output_json = str(
                job_output_dir / "transcript.json"
            )

        if log_file is None:
            log_file = str(
                job_output_dir / "pipeline.log"
            )

        _update_job_status_safely(
            job_id=job_id,
            status="processing"
        )

        worker_job_service = WorkerJobService(
            model_size=model_size,
            language=language,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
            log_file=log_file,
        )

        run_result = worker_job_service.run_job(
            input_audio=input_audio,
            normalized_audio=normalized_audio,
            output_json=output_json,
            job_id=job_id
        )

        if run_result.success:
            _update_job_status_safely(
                job_id=job_id,
                status="done"
            )

            _send_webhook_safely(
                webhook_url=webhook_url,
                job_id=job_id,
                status="done",
                error=None
            )

        else:
            _update_job_status_safely(
                job_id=job_id,
                status="failed",
                error_code="PIPELINE_FAILED",
                error_message=run_result.error
            )

            _send_webhook_safely(
                webhook_url=webhook_url,
                job_id=job_id,
                status="failed",
                error=run_result.error
            )

        return run_result.model_dump()

    finally:
        _delete_temp_file(
            downloaded_audio_path
        )