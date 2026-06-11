from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatusResponse(BaseModel):
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
    ready: bool = Field(
        ...,
        description="Whether the task has finished."
    )
    successful: bool = Field(
        ...,
        description="Whether the task finished successfully."
    )
    failed: bool = Field(
        ...,
        description="Whether the task failed."
    )
    error: Optional[str] = Field(
        None,
        description="Error message if task failed."
    )
    traceback: Optional[str] = Field(
        None,
        description="Celery traceback if task failed."
    )
    result: Optional[Any] = Field(
        None,
        description="Optional task result."
    )