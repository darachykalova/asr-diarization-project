from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SearchMode(str, Enum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"


class CallSegmentResponse(BaseModel):
    score: Optional[float] = Field(
        None,
        description="Search relevance score."
    )
    score_type: Optional[str] = Field(
        None,
        description="Search score type: keyword or semantic."
    )
    job_id: str = Field(
        ...,
        min_length=1,
        description="Processing job ID."
    )
    segment_id: int = Field(
        ...,
        ge=0,
        description="Transcript segment ID."
    )
    speaker: str = Field(
        ...,
        min_length=1,
        description="Speaker label."
    )
    start: float = Field(
        ...,
        ge=0,
        description="Segment start time in seconds."
    )
    end: float = Field(
        ...,
        ge=0,
        description="Segment end time in seconds."
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Transcript segment text."
    )
    embedding_source: Optional[str] = Field(
        None,
        description="Embedding source."
    )
    diarization_source: Optional[str] = Field(
        None,
        description="Diarization source."
    )
    alignment_source: Optional[str] = Field(
        None,
        description="Alignment source."
    )
    keyword_score: Optional[float] = Field(
        None,
        description="Exact keyword score used by semantic search."
    )
    semantic_score: Optional[float] = Field(
        None,
        description="Vector similarity score used by semantic search."
    )


class CallSegmentsResponse(BaseModel):
    job_id: str = Field(
        ...,
        min_length=1,
        description="Processing job ID."
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of returned segments."
    )
    segments: list[CallSegmentResponse] = Field(
        default_factory=list,
        description="Transcript segments for one processed call."
    )


class CallSearchResponse(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="Search query."
    )
    job_id: Optional[str] = Field(
        None,
        description="Optional job ID filter. If empty, search runs globally."
    )
    speaker: Optional[str] = Field(
        None,
        description="Optional speaker filter."
    )
    mode: SearchMode = Field(
        ...,
        description="Search mode."
    )
    limit: int = Field(
        ...,
        ge=1,
        le=100,
        description="Maximum number of results."
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of returned results."
    )
    results: list[CallSegmentResponse] = Field(
        default_factory=list,
        description="Search results."
    )