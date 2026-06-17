import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from api.auth import require_scope
from clients.minio_client import MinioStorageClient
from database import crud
from database.session import SessionLocal
from schemas.api.transcription_schema import TranscriptionTaskResponse
from tasks.audio_tasks import process_audio_task


router = APIRouter(
    prefix="/transcriptions",
    tags=["Transcriptions"]
)


MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


def _create_task_response(
    input_audio: str,
    include_input_audio: bool
) -> dict:
    job_id = str(uuid4())

    process_audio_task.apply_async(
        kwargs={
            "input_audio": input_audio,
            "job_id": job_id
        },
        task_id=job_id
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "input_audio": input_audio if include_input_audio else None
    }


async def _save_upload_to_temp_file(
    file: UploadFile
) -> tuple[str, int]:
    suffix = Path(file.filename or "audio").suffix

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix
    ) as temp_file:
        temp_path = temp_file.name
        total_size = 0

        while True:
            chunk = await file.read(CHUNK_SIZE)

            if not chunk:
                break

            total_size += len(chunk)

            if total_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="File too large. Maximum allowed size is 2 GB."
                )

            temp_file.write(chunk)

    return temp_path, total_size


def _upload_temp_file_to_minio(
    temp_path: str,
    object_key: str,
    content_type: str | None
) -> str:
    storage_client = MinioStorageClient()

    return storage_client.upload_file(
        local_path=temp_path,
        object_key=object_key,
        content_type=content_type
    )


def _delete_temp_file_safely(temp_path: str) -> None:
    try:
        Path(temp_path).unlink(
            missing_ok=True
        )

    except Exception:
        pass


def _create_upload_database_records(
    job_id: str,
    audio_key: str,
    filename: str,
    speaker_id: Optional[int],
    params: dict
) -> None:
    db = SessionLocal()

    try:
        if speaker_id is not None:
            speaker = crud.get_speaker(
                db=db,
                speaker_id=speaker_id
            )

            if speaker is None:
                raise ValueError(
                    f"Speaker not found: {speaker_id}"
                )

        crud.create_job(
            db=db,
            job_id=job_id,
            status="queued",
            audio_key=audio_key,
            params=params,
            idempotency_key=None
        )

        crud.create_recording(
            db=db,
            job_id=job_id,
            filename=filename,
            speaker_id=speaker_id
        )

    finally:
        db.close()


@router.post(
    "",
    response_model=TranscriptionTaskResponse,
    summary="Create transcription task from audio path",
    description="Creates a background transcription task using an existing audio file path.",
    dependencies=[Depends(require_scope("write"))]
)
async def create_transcription(audio_path: str):
    return await run_in_threadpool(
        _create_task_response,
        audio_path,
        False
    )


@router.post(
    "/upload",
    response_model=TranscriptionTaskResponse,
    summary="Upload audio file for transcription",
    description="Uploads an audio file to MinIO and starts asynchronous processing.",
    dependencies=[Depends(require_scope("write"))]
)
async def upload_transcription(
    file: UploadFile = File(
        ...,
        description="Audio file to process."
    ),
    language: str = "auto",
    speaker_id: Optional[int] = None
):
    job_id = str(uuid4())

    original_filename = file.filename or "audio.bin"
    object_key = f"jobs/{job_id}/{original_filename}"

    temp_path = None

    try:
        temp_path, file_size = await _save_upload_to_temp_file(
            file=file
        )

        await run_in_threadpool(
            _upload_temp_file_to_minio,
            temp_path,
            object_key,
            file.content_type
        )

    finally:
        if temp_path is not None:
            await run_in_threadpool(
                _delete_temp_file_safely,
                temp_path
            )

    params = {
        "speaker_id": speaker_id,
        "language": language,
        "storage": "minio",
        "file_size": file_size
    }

    try:
        await run_in_threadpool(
            _create_upload_database_records,
            job_id,
            object_key,
            original_filename,
            speaker_id,
            params
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        ) from error

    task_language = None if language == "auto" else language

    process_audio_task.apply_async(
        kwargs={
            "input_audio": object_key,
            "job_id": job_id,
            "language": task_language,
            "input_storage": "minio"
        },
        task_id=job_id
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "input_audio": object_key
    }