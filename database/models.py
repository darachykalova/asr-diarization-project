from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_created_at", "created_at"),
        Index("ix_jobs_finished_at", "finished_at"),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    audio_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)

    # Whisper model actually used for this job (auto-selected from audio
    # quality, or the user's explicit choice). Populated by the ASR step.
    model_used: Mapped[str | None] = mapped_column(String(20), nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(
        String(200),
        unique=True,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    transcript = relationship(
        "Transcript",
        back_populates="job",
        uselist=False
    )


class Transcript(Base):
    __tablename__ = "transcripts"
    __table_args__ = (
        # GIN index для полнотекстового поиска (ts_stat и @@-оператор)
        Index("ix_transcripts_fts", "full_text_vector", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id"),
        unique=True,
        index=True
    )

    status: Mapped[str] = mapped_column(String(50))
    success: Mapped[bool] = mapped_column(Boolean)
    full_text: Mapped[str] = mapped_column(Text)
    full_text_vector = mapped_column(TSVECTOR, nullable=True)

    language: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True
    )

    duration_sec: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    job = relationship(
        "Job",
        back_populates="transcript"
    )

    segments = relationship(
        "TranscriptSegment",
        back_populates="transcript",
        cascade="all, delete-orphan"
    )

    occurrences = relationship(
        "Occurrence",
        back_populates="transcript",
        cascade="all, delete-orphan"
    )


class TranscriptSegment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    transcript_id: Mapped[int] = mapped_column(
        ForeignKey("transcripts.id")
    )

    segment_id: Mapped[int] = mapped_column(Integer)

    speaker: Mapped[str] = mapped_column(String(50))

    speaker_id: Mapped[int | None] = mapped_column(
        ForeignKey("speakers.id"),
        nullable=True
    )

    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)

    words: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    overlap: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    transcript = relationship(
        "Transcript",
        back_populates="segments"
    )

    speaker_ref = relationship(
        "Speaker"
    )


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    kind: Mapped[str] = mapped_column(
        String(20),
        default="anonymous"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    recordings = relationship(
        "Recording",
        back_populates="speaker",
        cascade="all, delete-orphan"
    )

    occurrences = relationship(
        "Occurrence",
        back_populates="speaker",
        cascade="all, delete-orphan"
    )


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    job_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True
    )

    speaker_id: Mapped[int | None] = mapped_column(
        ForeignKey("speakers.id"),
        nullable=True
    )

    filename: Mapped[str] = mapped_column(
        String(255)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    speaker = relationship(
        "Speaker",
        back_populates="recordings"
    )


class Occurrence(Base):
    __tablename__ = "occurrences"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    speaker_id: Mapped[int] = mapped_column(
        ForeignKey("speakers.id")
    )

    transcript_id: Mapped[int] = mapped_column(
        ForeignKey("transcripts.id")
    )

    local_label: Mapped[str] = mapped_column(
        String(50)
    )

    match_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )

    speaker = relationship(
        "Speaker",
        back_populates="occurrences"
    )

    transcript = relationship(
        "Transcript",
        back_populates="occurrences"
    )


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="moderator")
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    access_logs = relationship(
        "TranscriptAccessLog",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class TranscriptAccessLog(Base):
    __tablename__ = "transcript_access_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("admin_users.id"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False, default="reveal")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    user = relationship("AdminUser", back_populates="access_logs")


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    value_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="string"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id"), nullable=True
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    key_hash: Mapped[str] = mapped_column(
        String(200),
        unique=True
    )

    scopes: Mapped[str] = mapped_column(
        String(200),
        default="read"
    )

    rate_limit: Mapped[int] = mapped_column(
        Integer,
        default=100
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_calls_started_at", "started_at"),
        Index("ix_calls_verdict", "verdict"),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    source: Mapped[str] = mapped_column(String(200), default="browser")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[str] = mapped_column(String(30), default="undetermined")
    scenario: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    ended_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_key: Mapped[str | None] = mapped_column(String(500), nullable=True)


class CallEvent(Base):
    __tablename__ = "call_events"
    __table_args__ = (
        Index("ix_call_events_call_id", "call_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), nullable=False)
    at: Mapped[float] = mapped_column(Float, default=0.0)
    speaker: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    scam_delta: Mapped[int] = mapped_column(Integer, default=0)
