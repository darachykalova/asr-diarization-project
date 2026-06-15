from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    audio_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

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