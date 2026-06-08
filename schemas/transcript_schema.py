from typing import Optional
from pydantic import BaseModel


class SpeechSegment(BaseModel):
    """
    Speech segment detected by VAD.
    """

    start: float
    end: float


class SpeakerSegment(BaseModel):
    """
    Segment with assigned speaker label.
    """

    start: float
    end: float
    speaker: str


class Word(BaseModel):
    """
    Recognized word with word-level timestamps.
    """

    word: str
    start: float
    end: float
    confidence: float


class TranscriptSegment(BaseModel):
    """
    Final transcript segment after ASR, diarization and alignment.
    """

    id: int
    start: float
    end: float
    speaker: str
    overlap: bool
    text: str
    words: list[Word]
    alignment_source: str


class SpeakerEmbedding(BaseModel):
    """
    Speaker embedding metadata.

    Current version stores placeholder embedding.
    Later vector will contain real voice embedding values.
    """

    speaker: str
    audio_path: str
    embedding_source: str
    vector: list[float]
    vector_dim: int


class TranscriptResult(BaseModel):
    """
    Full transcript result saved to JSON.
    """

    input_audio: str
    normalized_audio: str
    speech_segments: list[SpeechSegment]
    speaker_segments: list[SpeakerSegment]
    speaker_embeddings: list[SpeakerEmbedding]
    segments: list[TranscriptSegment]
    full_text: str

class PipelineRunResult(BaseModel):
    """
    Result of pipeline execution.

    Used to represent both successful and failed processing.
    Later this structure will be used by Celery worker jobs.
    """

    job_id: str
    status: str
    success: bool
    transcript: Optional[TranscriptResult] = None
    error: Optional[str] = None