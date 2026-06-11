from typing import Optional

from pydantic import BaseModel, Field, model_validator


class SpeechSegment(BaseModel):
    start: float = Field(
        ...,
        ge=0,
        description="Speech segment start time in seconds."
    )
    end: float = Field(
        ...,
        ge=0,
        description="Speech segment end time in seconds."
    )

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class SpeakerSegment(BaseModel):
    start: float = Field(
        ...,
        ge=0,
        description="Speaker segment start time in seconds."
    )
    end: float = Field(
        ...,
        ge=0,
        description="Speaker segment end time in seconds."
    )
    speaker: str = Field(
        ...,
        min_length=1,
        description="Speaker label, for example SPEAKER_00."
    )
    diarization_source: str = Field(
        "placeholder",
        description="Diarization source, for example pyannote."
    )

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class Word(BaseModel):
    word: str = Field(
        ...,
        min_length=1,
        description="Recognized word."
    )
    start: float = Field(
        ...,
        ge=0,
        description="Word start time in seconds."
    )
    end: float = Field(
        ...,
        ge=0,
        description="Word end time in seconds."
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description="Word recognition confidence from 0 to 1."
    )

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class TranscriptSegment(BaseModel):
    id: int = Field(
        ...,
        ge=0,
        description="Transcript segment index."
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
    speaker: str = Field(
        ...,
        min_length=1,
        description="Speaker label assigned to this segment."
    )
    overlap: bool = Field(
        False,
        description="Whether this segment contains overlapping speech."
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Recognized transcript text."
    )
    words: list[Word] = Field(
        default_factory=list,
        description="Word-level timestamps."
    )
    alignment_source: str = Field(
        ...,
        min_length=1,
        description="Alignment source."
    )
    diarization_source: str = Field(
        "placeholder",
        description="Diarization source."
    )

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")
        return self


class SpeakerEmbedding(BaseModel):
    speaker: str = Field(
        ...,
        min_length=1,
        description="Speaker label."
    )
    audio_path: str = Field(
        ...,
        min_length=1,
        description="Path to normalized audio file."
    )
    embedding_source: str = Field(
        ...,
        min_length=1,
        description="Speaker embedding source."
    )
    vector: list[float] = Field(
        default_factory=list,
        description="Speaker embedding vector."
    )
    vector_dim: int = Field(
        ...,
        ge=0,
        description="Speaker embedding vector dimension."
    )


class TranscriptResult(BaseModel):
    input_audio: str = Field(
        ...,
        min_length=1,
        description="Original uploaded audio path."
    )
    normalized_audio: str = Field(
        ...,
        min_length=1,
        description="Normalized audio path."
    )
    speech_segments: list[SpeechSegment] = Field(
        default_factory=list,
        description="Speech activity segments."
    )
    speaker_segments: list[SpeakerSegment] = Field(
        default_factory=list,
        description="Speaker diarization segments."
    )
    speaker_embeddings: list[SpeakerEmbedding] = Field(
        default_factory=list,
        description="Speaker embedding metadata."
    )
    segments: list[TranscriptSegment] = Field(
        default_factory=list,
        description="Final transcript segments."
    )
    full_text: str = Field(
        "",
        description="Full transcript text."
    )


class PipelineRunResult(BaseModel):
    job_id: str = Field(
        ...,
        min_length=1,
        description="Processing job ID."
    )
    status: str = Field(
        ...,
        min_length=1,
        description="Processing status."
    )
    success: bool = Field(
        ...,
        description="Whether processing finished successfully."
    )
    transcript: Optional[TranscriptResult] = Field(
        None,
        description="Transcript result if processing succeeded."
    )
    error: Optional[str] = Field(
        None,
        description="Error message if processing failed."
    )