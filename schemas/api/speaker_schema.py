from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SpeakerCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        description="Speaker name."
    )
    phone: Optional[str] = Field(
        None,
        description="Optional speaker phone number."
    )


class SpeakerUpdate(BaseModel):
    name: Optional[str] = Field(
        None,
        min_length=1,
        description="New speaker name."
    )
    phone: Optional[str] = Field(
        None,
        description="New speaker phone number."
    )


class SpeakerMergeRequest(BaseModel):
    target_speaker_id: int = Field(
        ...,
        description="Speaker ID that will remain after merge."
    )


class SpeakerResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class RecordingResponse(BaseModel):
    id: int
    job_id: str
    filename: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class SpeakerDeleteResponse(BaseModel):
    message: str


class SpeakerMergeResponse(BaseModel):
    message: str
    source_speaker_id: int
    target_speaker_id: int