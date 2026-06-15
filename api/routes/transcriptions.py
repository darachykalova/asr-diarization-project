from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from database import crud
from database.session import SessionLocal
from schemas.api.transcription_schema import TranscriptionTaskResponse
from tasks.audio_tasks import process_audio_task


router = APIRouter(
    prefix="/transcriptions",
    tags=["Transcriptions"]
)


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


def _save_uploaded_file(
    input_audio_path: Path,
    content: bytes
) -> None:
    input_audio_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(input_audio_path, "wb") as output_file:
        output_file.write(content)


def _create_recording_in_database(
    job_id: str,
    filename: str,
    speaker_id: Optional[int]
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
    description="Creates a background transcription task using an existing audio file path."
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
    description="Uploads an audio file and starts asynchronous processing."
)
async def upload_transcription(
    file: UploadFile = File(
        ...,
        description="Audio file to process."
    ),
    speaker_id: Optional[int] = None
):
    job_id = str(uuid4())

    upload_dir = Path("data/input/jobs") / job_id
    input_audio_path = upload_dir / file.filename

    content = await file.read()

    await run_in_threadpool(
        _save_uploaded_file,
        input_audio_path,
        content
    )

    try:
        await run_in_threadpool(
            _create_recording_in_database,
            job_id,
            file.filename,
            speaker_id
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        ) from error

    process_audio_task.apply_async(
        kwargs={
            "input_audio": str(input_audio_path),
            "job_id": job_id
        },
        task_id=job_id
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "input_audio": str(input_audio_path)
    }