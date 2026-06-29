from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from api.auth import require_scope
from clients.minio_client import MinioStorageClient
from database import crud
from services.qdrant_service import QdrantService


router = APIRouter(
    prefix="/transcripts",
    tags=["Transcripts"]
)


def _get_transcript_from_postgres(job_id: str) -> dict | None:
    return crud.get_transcript_by_job_id(job_id=job_id)


def _delete_transcript_everywhere(job_id: str) -> dict:
    clean_job_id = job_id.strip()

    if crud.get_transcript_by_job_id(job_id=clean_job_id) is None:
        return {"deleted": False, "reason": "not_found"}

    audio_key = crud.get_audio_key_by_job_id(job_id=clean_job_id)

    minio_deleted = False
    if audio_key:
        try:
            minio_deleted = MinioStorageClient().delete_file(audio_key)
        except Exception:
            minio_deleted = False

    qdrant_deleted = QdrantService().delete_job_segments(job_id=clean_job_id)
    postgres_deleted = crud.delete_transcript_by_job_id(job_id=clean_job_id)

    return {
        "deleted": postgres_deleted,
        "job_id": clean_job_id,
        "audio_key": audio_key,
        "minio_deleted": minio_deleted,
        "qdrant_deleted": qdrant_deleted,
        "postgres_deleted": postgres_deleted,
    }


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
    "",
    summary="List transcripts",
    description="Returns paginated list of transcripts with optional filters.",
    dependencies=[Depends(require_scope("read"))]
)
async def list_transcripts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    speaker_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
):
    return await run_in_threadpool(
        crud.list_transcripts,
        page=page,
        page_size=page_size,
        speaker_id=speaker_id,
        status=status,
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


@router.delete(
    "/{job_id}",
    summary="Delete transcript",
    description=(
        "Deletes transcript from Postgres, audio file from MinIO, "
        "and transcript vectors from Qdrant."
    ),
    dependencies=[Depends(require_scope("write"))]
)
async def delete_transcript(job_id: str):
    result = await run_in_threadpool(
        _delete_transcript_everywhere,
        job_id
    )

    if not result.get("deleted"):
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for job: {job_id}"
        )

    return {
        "message": f"Transcript {job_id.strip()} deleted",
        "job_id": result["job_id"],
        "audio_key": result["audio_key"],
        "minio_deleted": result["minio_deleted"],
        "qdrant_deleted": result["qdrant_deleted"],
        "postgres_deleted": result["postgres_deleted"]
    }


@router.get(
    "/{job_id}/segments",
    summary="Get transcript segments",
    description="Returns paginated segments for a transcript, with optional speaker filter.",
    dependencies=[Depends(require_scope("read"))]
)
async def get_segments(
    job_id: str,
    speaker_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    result = await run_in_threadpool(
        crud.get_segments_by_job_id,
        job_id=job_id,
        speaker_id=speaker_id,
        page=page,
        page_size=page_size,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for job: {job_id}"
        )

    return result


@router.get(
    "/{job_id}/export",
    summary="Export transcript",
    description="Export transcript as TXT, SRT or VTT.",
    dependencies=[Depends(require_scope("read"))]
)
async def export_transcript(
    job_id: str,
    format: Literal["txt", "srt", "vtt"] = Query(
        default="txt",
        description="Export format"
    )
):
    transcript = await run_in_threadpool(
        _get_transcript_from_postgres,
        job_id
    )

    if transcript is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for job: {job_id}"
        )

    if format == "txt":
        return _file_response(
            content=_build_txt(transcript),
            filename=f"transcript_{job_id}.txt",
            media_type="text/plain"
        )

    if format == "srt":
        return _file_response(
            content=_build_srt(transcript),
            filename=f"transcript_{job_id}.srt",
            media_type="text/plain"
        )

    return _file_response(
        content=_build_vtt(transcript),
        filename=f"transcript_{job_id}.vtt",
        media_type="text/vtt"
    )
