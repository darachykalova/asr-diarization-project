from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50))
    success: Mapped[bool] = mapped_column(Boolean)
    full_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    segments = relationship(
        "TranscriptSegment",
        back_populates="transcript",
        cascade="all, delete-orphan"
    )


class TranscriptSegment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transcript_id: Mapped[int] = mapped_column(ForeignKey("transcripts.id"))
    segment_id: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(50))
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)

    transcript = relationship(
        "Transcript",
        back_populates="segments"
    )