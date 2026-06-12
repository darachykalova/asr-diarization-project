from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from database.repository import TranscriptRepository


router = APIRouter(
    prefix="/transcripts",
    tags=["Transcripts"]
)


def _get_transcript_from_postgres(job_id: str) -> dict | None:
    repository = TranscriptRepository()
    return repository.get_transcript_by_job_id(job_id)


@router.get(
    "/{job_id}",
    summary="Get transcript result",
    description="Returns transcript result from Postgres by job ID."
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