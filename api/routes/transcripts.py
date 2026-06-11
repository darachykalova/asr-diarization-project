import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from schemas.api.transcript_response_schema import TranscriptResponse


router = APIRouter(
    prefix="/transcripts",
    tags=["Transcripts"]
)


@router.get(
    "/{job_id}",
    response_model=TranscriptResponse,
    summary="Get transcript result",
    description="Returns transcript JSON generated for a completed job."
)
def get_transcript(job_id: str):
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

    with open(
        transcript_path,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)