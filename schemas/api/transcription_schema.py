from typing import Optional

from pydantic import BaseModel, Field


class TranscriptionTaskResponse(BaseModel):
    job_id: str = Field(
        ...,
        min_length=1,
        description="Unique background processing job ID."
    )
    celery_state: str = Field(
        ...,
        min_length=1,
        description="Raw Celery task state."
    )
    status: str = Field(
        ...,
        min_length=1,
        description="Business-level task status."
    )
    status_url: str = Field(
        ...,
        min_length=1,
        description="Endpoint URL for checking job status."
    )
    input_audio: Optional[str] = Field(
        None,
        description="Path to uploaded audio file."
    )