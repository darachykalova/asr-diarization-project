from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class JobStatusResponse(BaseModel):
    job_id: str = Field(..., description="Unique background processing job ID.")
    status: str = Field(..., description="queued / processing / done / failed / partial")
    progress: int = Field(0, ge=0, le=100, description="Completion percentage 0–100.")
    error_code: Optional[str] = Field(None, description="Machine-readable error code.")
    error_message: Optional[str] = Field(None, description="Human-readable error description.")
    model_used: Optional[str] = Field(None, description="Whisper model used for this job.")
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
