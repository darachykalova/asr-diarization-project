from sqlalchemy.orm import Session

from database.models import Recording, Speaker


def create_speaker(
    db: Session,
    name: str,
    phone: str | None = None
) -> Speaker:
    speaker = Speaker(
        name=name,
        phone=phone
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