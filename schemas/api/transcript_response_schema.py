from typing import Optional

from pydantic import BaseModel, Field

from schemas.transcript_schema import TranscriptResult


class TranscriptResponse(BaseModel):
    job_id: str = Field(
        ...,
        description="Processing job ID."
    )
    status: str = Field(
        ...,
        description="Processing status."
    )
    success: bool = Field(
        ...,
        description="Whether processing finished successfully."
    )
    transcript: Optional[TranscriptResult] = Field(
        None,
        description="Transcript result."
    )
    error: Optional[str] = Field(
        None,
        description="Error message if processing failed."
    )