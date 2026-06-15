from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import crud
from database.session import SessionLocal
from schemas.api.speaker_schema import (
    RecordingResponse,
    SpeakerCreate,
    SpeakerResponse,
)


router = APIRouter(
    prefix="/speakers",
    tags=["Speakers"]
)


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


@router.post(
    "",
    response_model=SpeakerResponse,
    summary="Create speaker",
    description="Creates a new speaker in Postgres."
)
def create_speaker(
    data: SpeakerCreate,
    db: Session = Depends(get_db)
):
    return crud.create_speaker(
        db=db,
        name=data.name,
        phone=data.phone
    )


@router.get(
    "",
    response_model=list[SpeakerResponse],
    summary="List speakers",
    description="Returns all speakers from Postgres."
)
def list_speakers(
    db: Session = Depends(get_db)
):
    return crud.get_all_speakers(
        db=db
    )


@router.get(
    "/{speaker_id}/recordings",
    response_model=list[RecordingResponse],
    summary="Get speaker recordings",
    description="Returns all audio recordings linked to selected speaker."
)
def get_speaker_recordings(
    speaker_id: int,
    db: Session = Depends(get_db)
):
    speaker = crud.get_speaker(
        db=db,
        speaker_id=speaker_id
    )

    if speaker is None:
        raise HTTPException(
            status_code=404,
            detail="Speaker not found"
        )

    return crud.get_recordings_by_speaker(
        db=db,
        speaker_id=speaker_id
    )