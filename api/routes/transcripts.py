from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from api.auth import require_scope
from database.repository import TranscriptRepository


router = APIRouter(
    prefix="/transcripts",
    tags=["Transcripts"]
)


def _get_transcript_from_postgres(job_id: str) -> dict | None:
    repository = TranscriptRepository()

    return repository.get_transcript_by_job_id(
        job_id=job_id
    )


def _format_timestamp(
    seconds: float,
    srt: bool = True
) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))

    if srt:
        return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


def _build_txt(transcript: dict) -> str:
    lines = []

    for segment in transcript["transcript"]["segments"]:
        lines.append(
            f"[{segment['speaker']}] {segment['text']}"
        )

    return "\n".join(lines)


def _build_srt(transcript: dict) -> str:
    blocks = []

    for index, segment in enumerate(
        transcript["transcript"]["segments"],
        start=1
    ):
        start = _format_timestamp(
            segment["start"],
            srt=True
        )

        end = _format_timestamp(
            segment["end"],
            srt=True
        )

        blocks.append(
            (
                f"{index}\n"
                f"{start} --> {end}\n"
                f"[{segment['speaker']}] {segment['text']}\n"
            )
        )

    return "\n".join(blocks)


def _build_vtt(transcript: dict) -> str:
    blocks = ["WEBVTT\n"]

    for segment in transcript["transcript"]["segments"]:
        start = _format_timestamp(
            segment["start"],
            srt=False
        )

        end = _format_timestamp(
            segment["end"],
            srt=False
        )

        blocks.append(
            (
                f"{start} --> {end}\n"
                f"[{segment['speaker']}] {segment['text']}\n"
            )
        )

    return "\n".join(blocks)


def _file_response(
    content: str,
    filename: str,
    media_type: str
) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"'
        }
    )


@router.get(
    "/{job_id}",
    summary="Get transcript result",
    description="Returns transcript result from Postgres by job ID.",
    dependencies=[Depends(require_scope("read"))]
)
async def get_transcript(job_id: str):
    transcript = await run_in_threadpool(
        _get_transcript_from_postgres,
        job_id
    )

    if transcript is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for job: {job_id}"
        )

    return transcript


@router.get(
    "/{job_id}/export/txt",
    summary="Export transcript as TXT",
    dependencies=[Depends(require_scope("read"))]
)
async def export_txt(job_id: str):
    transcript = await run_in_threadpool(
        _get_transcript_from_postgres,
        job_id
    )

    if transcript is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for job: {job_id}"
        )

    return _file_response(
        content=_build_txt(transcript),
        filename=f"transcript_{job_id}.txt",
        media_type="text/plain"
    )


@router.get(
    "/{job_id}/export/srt",
    summary="Export transcript as SRT",
    dependencies=[Depends(require_scope("read"))]
)
async def export_srt(job_id: str):
    transcript = await run_in_threadpool(
        _get_transcript_from_postgres,
        job_id
    )

    if transcript is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for job: {job_id}"
        )

    return _file_response(
        content=_build_srt(transcript),
        filename=f"transcript_{job_id}.srt",
        media_type="text/plain"
    )


@router.get(
    "/{job_id}/export/vtt",
    summary="Export transcript as VTT",
    dependencies=[Depends(require_scope("read"))]
)
async def export_vtt(job_id: str):
    transcript = await run_in_threadpool(
        _get_transcript_from_postgres,
        job_id
    )

    if transcript is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for job: {job_id}"
        )

    return _file_response(
        content=_build_vtt(transcript),
        filename=f"transcript_{job_id}.vtt",
        media_type="text/vtt"
    )