from typing import Optional

from pydantic import BaseModel, Field


class JobStatusResponse(BaseModel):
    job_id: str = Field(
        ...,
        min_length=1,
        description="Unique background processing job ID."
    )
    status: str = Field(
        ...,
        min_length=1,
        description="Current job status: queued, processing, done or failed."
    )
    error: Optional[str] = Field(
        None,
        description="Error message if task failed."
    )