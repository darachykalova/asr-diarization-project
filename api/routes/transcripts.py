import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from schemas.api.transcript_response_schema import TranscriptResponse


router = APIRouter(
    prefix="/transcripts",
    tags=["Transcripts"]
)


def _load_transcript_json(
    transcript_path: Path
) -> dict:
    with open(
        transcript_path,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


@router.get(
    "/{job_id}",
    response_model=TranscriptResponse,
    summary="Get transcript result",
    description="Returns transcript JSON generated for a completed job."
)
async def get_transcript(job_id: str):
    transcript_path = (
        Path("data/output/jobs")
        / job_id
        / "transcript.json"
    )

    if not transcript_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for job: {job_id}"
        )

    return await run_in_threadpool(
        _load_transcript_json,
        transcript_path
    )