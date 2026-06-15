from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.auth import require_scope
from database import crud
from database.session import SessionLocal
from schemas.api.speaker_schema import (
    RecordingResponse,
    SpeakerCreate,
    SpeakerDeleteResponse,
    SpeakerMergeRequest,
    SpeakerMergeResponse,
    SpeakerResponse,
    SpeakerUpdate,
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
    description="Creates a new speaker in Postgres.",
    dependencies=[Depends(require_scope("write"))]
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
    description="Returns all speakers from Postgres.",
    dependencies=[Depends(require_scope("read"))]
)
def list_speakers(
    db: Session = Depends(get_db)
):
    return crud.get_all_speakers(
        db=db
    )


@router.patch(
    "/{speaker_id}",
    response_model=SpeakerResponse,
    summary="Update speaker",
    description="Updates speaker name or phone.",
    dependencies=[Depends(require_scope("write"))]
)
def update_speaker(
    speaker_id: int,
    data: SpeakerUpdate,
    db: Session = Depends(get_db)
):
    speaker = crud.update_speaker(
        db=db,
        speaker_id=speaker_id,
        name=data.name,
        phone=data.phone
    )

    if speaker is None:
        raise HTTPException(
            status_code=404,
            detail="Speaker not found"
        )

    return speaker


@router.delete(
    "/{speaker_id}",
    response_model=SpeakerDeleteResponse,
    summary="Delete speaker",
    description="Deletes speaker and all linked recordings and occurrences.",
    dependencies=[Depends(require_scope("write"))]
)
def delete_speaker(
    speaker_id: int,
    db: Session = Depends(get_db)
):
    deleted = crud.delete_speaker(
        db=db,
        speaker_id=speaker_id
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Speaker not found"
        )

    return {
        "message": f"Speaker {speaker_id} deleted"
    }


@router.post(
    "/{speaker_id}/merge",
    response_model=SpeakerMergeResponse,
    summary="Merge speakers",
    description=(
        "Merges source speaker into target speaker. "
        "All recordings and occurrences are reassigned. "
        "Source speaker is deleted."
    ),
    dependencies=[Depends(require_scope("write"))]
)
def merge_speakers(
    speaker_id: int,
    data: SpeakerMergeRequest,
    db: Session = Depends(get_db)
):
    if speaker_id == data.target_speaker_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot merge speaker with itself"
        )

    result = crud.merge_speakers(
        db=db,
        source_speaker_id=speaker_id,
        target_speaker_id=data.target_speaker_id
    )

    if result == "source_not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Source speaker {speaker_id} not found"
        )

    if result == "target_not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Target speaker {data.target_speaker_id} not found"
        )

    return {
        "message": (
            f"Speaker {speaker_id} merged into "
            f"{data.target_speaker_id}"
        ),
        "source_speaker_id": speaker_id,
        "target_speaker_id": data.target_speaker_id
    }


@router.get(
    "/{speaker_id}/recordings",
    response_model=list[RecordingResponse],
    summary="Get speaker recordings",
    description="Returns all audio recordings linked to selected speaker.",
    dependencies=[Depends(require_scope("read"))]
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