from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, UploadFile
from starlette.concurrency import run_in_threadpool

from schemas.api.transcription_schema import TranscriptionTaskResponse
from tasks import process_audio_task


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
    )
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