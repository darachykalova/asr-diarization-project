from datetime import datetime
from math import ceil

from sqlalchemy.orm import Session

from database.models import (
    Job,
    Occurrence,
    Recording,
    Speaker,
    TranscriptSegment,
)


def create_speaker(
    db: Session,
    name: str,
    phone: str | None = None
) -> Speaker:
    speaker = Speaker(
        name=name,
        phone=phone,
        kind="registered"
    )

    db.add(speaker)
    db.commit()
    db.refresh(speaker)

    return speaker


def create_anonymous_speaker(
    db: Session,
    name: str = "Unknown speaker"
) -> Speaker:
    speaker = Speaker(
        name=name,
        phone=None,
        kind="anonymous"
    )

    db.add(speaker)
    db.commit()
    db.refresh(speaker)

    return speaker


def get_speaker(
    db: Session,
    speaker_id: int
) -> Speaker | None:
    return (
        db.query(Speaker)
        .filter(Speaker.id == speaker_id)
        .first()
    )


def get_all_speakers(
    db: Session
) -> list[Speaker]:
    return (
        db.query(Speaker)
        .order_by(Speaker.id)
        .all()
    )


def get_speakers_paginated(
    db: Session,
    page: int = 1,
    page_size: int = 20
) -> dict:
    total = db.query(Speaker).count()

    offset = (page - 1) * page_size

    items = (
        db.query(Speaker)
        .order_by(Speaker.id)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    pages = ceil(total / page_size) if total else 0

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages
    }


def update_speaker(
    db: Session,
    speaker_id: int,
    name: str | None = None,
    phone: str | None = None
) -> Speaker | None:
    speaker = get_speaker(
        db=db,
        speaker_id=speaker_id
    )

    if speaker is None:
        return None

    if name is not None:
        speaker.name = name

    if phone is not None:
        speaker.phone = phone

    db.commit()
    db.refresh(speaker)

    return speaker


def delete_speaker(
    db: Session,
    speaker_id: int
) -> bool:
    speaker = get_speaker(
        db=db,
        speaker_id=speaker_id
    )

    if speaker is None:
        return False

    db.delete(speaker)
    db.commit()

    return True


def merge_speakers(
    db: Session,
    source_speaker_id: int,
    target_speaker_id: int
) -> str:
    source_speaker = get_speaker(
        db=db,
        speaker_id=source_speaker_id
    )

    if source_speaker is None:
        return "source_not_found"

    target_speaker = get_speaker(
        db=db,
        speaker_id=target_speaker_id
    )

    if target_speaker is None:
        return "target_not_found"

    (
        db.query(Recording)
        .filter(Recording.speaker_id == source_speaker_id)
        .update(
            {"speaker_id": target_speaker_id},
            synchronize_session=False
        )
    )

    (
        db.query(Occurrence)
        .filter(Occurrence.speaker_id == source_speaker_id)
        .update(
            {"speaker_id": target_speaker_id},
            synchronize_session=False
        )
    )

    (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.speaker_id == source_speaker_id)
        .update(
            {"speaker_id": target_speaker_id},
            synchronize_session=False
        )
    )

    db.delete(source_speaker)
    db.commit()

    return "merged"


def create_occurrence(
    db: Session,
    speaker_id: int,
    transcript_id: int,
    local_label: str,
    match_score: float | None = None
) -> Occurrence:
    occurrence = Occurrence(
        speaker_id=speaker_id,
        transcript_id=transcript_id,
        local_label=local_label,
        match_score=match_score
    )

    db.add(occurrence)
    db.commit()
    db.refresh(occurrence)

    return occurrence


def get_occurrences_by_speaker(
    db: Session,
    speaker_id: int
) -> list[Occurrence]:
    return (
        db.query(Occurrence)
        .filter(Occurrence.speaker_id == speaker_id)
        .order_by(Occurrence.id)
        .all()
    )


def update_segments_speaker_id(
    db: Session,
    transcript_id: int,
    local_label: str,
    speaker_id: int
) -> None:
    (
        db.query(TranscriptSegment)
        .filter(
            TranscriptSegment.transcript_id == transcript_id,
            TranscriptSegment.speaker == local_label
        )
        .update(
            {"speaker_id": speaker_id},
            synchronize_session=False
        )
    )

    db.commit()


def create_recording(
    db: Session,
    job_id: str,
    filename: str,
    speaker_id: int | None = None
) -> Recording:
    recording = Recording(
        job_id=job_id,
        filename=filename,
        speaker_id=speaker_id
    )

    db.add(recording)
    db.commit()
    db.refresh(recording)

    return recording


def get_recordings_by_speaker(
    db: Session,
    speaker_id: int
) -> list[Recording]:
    return (
        db.query(Recording)
        .filter(Recording.speaker_id == speaker_id)
        .order_by(Recording.id)
        .all()
    )


def get_recording_by_job_id(
    db: Session,
    job_id: str
) -> Recording | None:
    return (
        db.query(Recording)
        .filter(Recording.job_id == job_id)
        .first()
    )


def create_job(
    db: Session,
    job_id: str,
    status: str = "queued",
    audio_key: str | None = None,
    params: dict | None = None,
    idempotency_key: str | None = None
) -> Job:
    job = Job(
        id=job_id,
        status=status,
        audio_key=audio_key,
        params=params,
        idempotency_key=idempotency_key
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


def get_job_by_id(
    db: Session,
    job_id: str
) -> Job | None:
    return (
        db.query(Job)
        .filter(Job.id == job_id)
        .first()
    )


def get_job_by_idempotency_key(
    db: Session,
    idempotency_key: str
) -> Job | None:
    return (
        db.query(Job)
        .filter(Job.idempotency_key == idempotency_key)
        .first()
    )


def update_job_status(
    db: Session,
    job_id: str,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None
) -> Job | None:
    job = get_job_by_id(
        db=db,
        job_id=job_id
    )

    if job is None:
        return None

    job.status = status
    job.error_code = error_code
    job.error_message = error_message

    if status == "processing":
        job.started_at = datetime.utcnow()

    if status in {"done", "failed", "partial"}:
        job.finished_at = datetime.utcnow()

    db.commit()
    db.refresh(job)

    return job