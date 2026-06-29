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
    kind: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class OccurrenceResponse(BaseModel):
    transcript_id: int
    local_label: str
    match_score: Optional[float]

    model_config = {"from_attributes": True}


class SpeakerDetailResponse(SpeakerResponse):
    occurrences: list[OccurrenceResponse] = []


class SpeakersPageResponse(BaseModel):
    items: list[SpeakerResponse]
    page: int
    page_size: int
    total: int
    pages: int


class RecordingResponse(BaseModel):
    job_id: str
    filename: str
    local_label: str
    match_score: Optional[float]
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
