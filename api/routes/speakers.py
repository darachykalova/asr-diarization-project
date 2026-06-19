import logging
import tempfile
import wave
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from api.auth import require_scope
from database import crud
from database.session import SessionLocal
from schemas.api.speaker_schema import (
    RecordingResponse,
    SpeakerDeleteResponse,
    SpeakerMergeRequest,
    SpeakerMergeResponse,
    SpeakerResponse,
    SpeakersPageResponse,
    SpeakerUpdate,
)
from services.audio_service import normalize_audio
from services.speaker_identification_service import SpeakerIdentificationService
from services.voice_embedding_service import VoiceEmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/speakers", tags=["Speakers"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_voice_embedding(audio: UploadFile) -> list[float]:
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    tmp_raw = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_raw.close()
    tmp_wav.close()

    try:
        with open(tmp_raw.name, "wb") as f:
            f.write(audio.file.read())

        normalized = normalize_audio(
            input_path=tmp_raw.name,
            output_path=tmp_wav.name
        )

        with wave.open(normalized, "rb") as wf:
            duration = wf.getnframes() / wf.getframerate()

        if duration < 10.0:
            raise HTTPException(
                status_code=400,
                detail="audio too short, minimum 10 seconds"
            )

        embedding = VoiceEmbeddingService().extract_embedding(normalized)

        if embedding is None:
            raise HTTPException(
                status_code=422,
                detail="failed to extract voice embedding"
            )

        return embedding

    finally:
        Path(tmp_raw.name).unlink(missing_ok=True)
        Path(tmp_wav.name).unlink(missing_ok=True)


@router.post(
    "",
    response_model=SpeakerResponse,
    summary="Create speaker",
    description=(
        "Creates a new registered speaker. "
        "Optionally accepts an audio sample (>= 10 s) to register the speaker's voice "
        "in the vector database for cross-recording identification."
    ),
    dependencies=[Depends(require_scope("write"))]
)
def create_speaker(
    name: str = Form(..., min_length=1, description="Speaker display name"),
    phone: Optional[str] = Form(None, description="Optional phone number"),
    audio: Optional[UploadFile] = File(None, description="Audio sample >= 10 s"),
    db: Session = Depends(get_db)
):
    embedding: list[float] | None = None

    if audio is not None:
        embedding = _extract_voice_embedding(audio)

    speaker = crud.create_speaker(db=db, name=name, phone=phone)

    if embedding is not None:
        SpeakerIdentificationService().save_embedding(
            speaker_id=speaker.id,
            embedding=embedding
        )
        logger.info("Registered voice for speaker_id=%s", speaker.id)

    return speaker


@router.get(
    "",
    response_model=SpeakersPageResponse,
    summary="List speakers",
    description="Returns speakers from Postgres with pagination.",
    dependencies=[Depends(require_scope("read"))]
)
def list_speakers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    return crud.get_speakers_paginated(db=db, page=page, page_size=page_size)


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
        raise HTTPException(status_code=404, detail="Speaker not found")
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
    deleted = crud.delete_speaker(db=db, speaker_id=speaker_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return {"message": f"Speaker {speaker_id} deleted"}


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
        raise HTTPException(status_code=400, detail="Cannot merge speaker with itself")

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
        "message": f"Speaker {speaker_id} merged into {data.target_speaker_id}",
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
    speaker = crud.get_speaker(db=db, speaker_id=speaker_id)
    if speaker is None:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return crud.get_recordings_by_speaker(db=db, speaker_id=speaker_id)
