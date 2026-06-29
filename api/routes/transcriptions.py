import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, HttpUrl
from starlette.concurrency import run_in_threadpool

from api.auth import require_scope
from clients.minio_client import MinioStorageClient
from database import crud
from database.session import SessionLocal
from schemas.api.transcription_schema import TranscriptionTaskResponse
from services.audio_quality_service import WhisperModelChoice, resolve_user_model
from services.audio_service import check_audio_file, SUPPORTED_EXTENSIONS
from tasks.audio_tasks import build_pipeline_chain


router = APIRouter(
    prefix="/transcriptions",
    tags=["Transcriptions"]
)


MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024


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
    "/upload",
    response_model=TranscriptionTaskResponse,
    status_code=202,
    summary="Upload audio file for transcription",
    description="Uploads an audio file to MinIO and starts asynchronous processing.",
    dependencies=[Depends(require_scope("write"))]
)
async def upload_transcription(
    file: UploadFile = File(..., description="Audio file to process."),
    language: str = "auto",
    speaker_id: Optional[int] = None,
    min_speakers: Optional[int] = None,
    max_speakers: Optional[int] = None,
    initial_prompt: Optional[str] = None,
    webhook_url: Optional[str] = None,
    whisper_model: Optional[WhisperModelChoice] = None,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    try:
        resolved_model = resolve_user_model(whisper_model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Idempotency: return existing job if key already seen
    if idempotency_key:
        db = SessionLocal()
        try:
            existing = crud.get_job_by_idempotency_key(db=db, idempotency_key=idempotency_key)
        finally:
            db.close()
        if existing is not None:
            return {
                "job_id": existing.id,
                "status": existing.status,
                "input_audio": existing.audio_key,
            }

    job_id = str(uuid4())

    original_filename = file.filename or "audio.bin"
    object_key = f"jobs/{job_id}/{original_filename}"

    temp_path = None

    try:
        temp_path, file_size = await _save_upload_to_temp_file(file=file)

        try:
            await run_in_threadpool(
                check_audio_file,
                temp_path,
                original_filename,
                file.content_type,
            )
        except ValueError as exc:
            status_code = 413 if "exceeds" in str(exc) else 415
            raise HTTPException(status_code=status_code, detail=str(exc))

        await run_in_threadpool(
            _upload_temp_file_to_minio,
            temp_path,
            object_key,
            file.content_type,
        )

    finally:
        if temp_path is not None:
            await run_in_threadpool(_delete_temp_file_safely, temp_path)

    params = {
        "speaker_id": speaker_id,
        "language": language,
        "storage": "minio",
        "file_size": file_size,
        "min_speakers": min_speakers,
        "max_speakers": max_speakers,
        "initial_prompt": initial_prompt,
        "webhook_url": webhook_url,
        "whisper_model": resolved_model,
    }

    try:
        await run_in_threadpool(
            _create_upload_database_records,
            job_id,
            object_key,
            original_filename,
            speaker_id,
            params,
        )

    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    # Save idempotency key now that the job record exists
    if idempotency_key:
        db = SessionLocal()
        try:
            job = crud.get_job_by_id(db=db, job_id=job_id)
            if job:
                job.idempotency_key = idempotency_key
                db.commit()
        finally:
            db.close()

    task_language = None if language == "auto" else language

    build_pipeline_chain(
        job_id=job_id,
        input_key=object_key,
        language=task_language,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
        whisper_model=resolved_model,
        initial_prompt=initial_prompt,
        webhook_url=webhook_url,
    ).apply_async(task_id=job_id)

    return {
        "job_id": job_id,
        "status": "queued",
        "input_audio": object_key,
    }


class UrlTranscriptionRequest(BaseModel):
    audio_url: HttpUrl
    language: str = "auto"
    speaker_id: Optional[int] = None
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None
    initial_prompt: Optional[str] = None
    webhook_url: Optional[str] = None
    whisper_model: Optional[WhisperModelChoice] = None


def _download_url_to_temp(url: str) -> tuple[str, str]:
    with httpx.stream("GET", url, timeout=60, follow_redirects=True) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        suffix = Path(str(url)).suffix.lower() or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                tmp.write(chunk)
            return tmp.name, content_type


@router.post(
    "/url",
    response_model=TranscriptionTaskResponse,
    status_code=202,
    summary="Submit audio URL for transcription",
    description="Downloads audio from URL (HTTP/presigned), uploads to MinIO, starts processing.",
    dependencies=[Depends(require_scope("write"))]
)
async def transcribe_from_url(
    body: UrlTranscriptionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
):
    try:
        resolved_model = resolve_user_model(body.whisper_model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if idempotency_key:
        db = SessionLocal()
        try:
            existing = crud.get_job_by_idempotency_key(db=db, idempotency_key=idempotency_key)
        finally:
            db.close()
        if existing is not None:
            return {"job_id": existing.id, "status": existing.status, "input_audio": existing.audio_key}

    job_id = str(uuid4())
    url_str = str(body.audio_url)
    filename = Path(url_str.split("?")[0]).name or "audio.bin"
    object_key = f"jobs/{job_id}/{filename}"
    temp_path = None

    try:
        try:
            temp_path, content_type = await run_in_threadpool(_download_url_to_temp, url_str)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download audio: HTTP {exc.response.status_code}")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to download audio: {exc}")

        try:
            await run_in_threadpool(check_audio_file, temp_path, filename, content_type)
        except ValueError as exc:
            status_code = 413 if "exceeds" in str(exc) else 415
            raise HTTPException(status_code=status_code, detail=str(exc))

        await run_in_threadpool(_upload_temp_file_to_minio, temp_path, object_key, content_type)

    finally:
        if temp_path is not None:
            await run_in_threadpool(_delete_temp_file_safely, temp_path)

    params = {
        "audio_url": url_str,
        "language": body.language,
        "storage": "minio",
        "min_speakers": body.min_speakers,
        "max_speakers": body.max_speakers,
        "initial_prompt": body.initial_prompt,
        "webhook_url": body.webhook_url,
        "whisper_model": resolved_model,
    }

    try:
        await run_in_threadpool(
            _create_upload_database_records,
            job_id, object_key, filename, body.speaker_id, params,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    if idempotency_key:
        db = SessionLocal()
        try:
            job = crud.get_job_by_id(db=db, job_id=job_id)
            if job:
                job.idempotency_key = idempotency_key
                db.commit()
        finally:
            db.close()

    task_language = None if body.language == "auto" else body.language

    build_pipeline_chain(
        job_id=job_id,
        input_key=object_key,
        language=task_language,
        min_speakers=body.min_speakers,
        max_speakers=body.max_speakers,
        whisper_model=resolved_model,
        initial_prompt=body.initial_prompt,
        webhook_url=body.webhook_url,
    ).apply_async(task_id=job_id)

    return {"job_id": job_id, "status": "queued", "input_audio": object_key}
