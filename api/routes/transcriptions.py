from pathlib import Path
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, UploadFile, File

from celery_app import celery_app
from tasks import process_audio_task
from schemas.api.transcription_schema import TranscriptionTaskResponse


CELERY_STATUS_MAP = {
    "PENDING": "queued",
    "RECEIVED": "queued",
    "STARTED": "processing",
    "SUCCESS": "done",
    "FAILURE": "failed",
    "RETRY": "retrying",
    "REVOKED": "revoked",
}


router = APIRouter(
    prefix="/transcriptions",
    tags=["Transcriptions"]
)


@router.post(
    "",
    response_model=TranscriptionTaskResponse,
    summary="Create transcription task from audio path",
    description="Creates a background transcription task using an existing audio file path."
)
def create_transcription(audio_path: str):
    job_id = str(uuid4())

    process_audio_task.apply_async(
        kwargs={
            "input_audio": audio_path,
            "job_id": job_id
        },
        task_id=job_id
    )

    task_result = AsyncResult(
        job_id,
        app=celery_app
    )

    return {
        "job_id": job_id,
        "celery_state": task_result.state,
        "status": CELERY_STATUS_MAP.get(
            task_result.state,
            task_result.state
        ),
        "status_url": f"/jobs/{job_id}",
        "input_audio": None
    }


@router.post(
    "/upload",
    response_model=TranscriptionTaskResponse,
    summary="Upload audio file for transcription",
    description="Uploads an audio file and starts asynchronous processing."
)
async def upload_transcription(
    file: UploadFile = File(
        ...,
        description="Audio file to process."
    )
):
    job_id = str(uuid4())

    upload_dir = Path("data/input/jobs") / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    input_audio_path = upload_dir / file.filename

    with open(input_audio_path, "wb") as output_file:
        content = await file.read()
        output_file.write(content)

    process_audio_task.apply_async(
        kwargs={
            "input_audio": str(input_audio_path),
            "job_id": job_id
        },
        task_id=job_id
    )

    task_result = AsyncResult(
        job_id,
        app=celery_app
    )

    return {
        "job_id": job_id,
        "celery_state": task_result.state,
        "status": CELERY_STATUS_MAP.get(
            task_result.state,
            task_result.state
        ),
        "status_url": f"/jobs/{job_id}",
        "input_audio": str(input_audio_path)
    }