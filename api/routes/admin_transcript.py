from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import get_db
from api.auth_users import get_current_user
from database import crud
from database.models import AdminUser

router = APIRouter(prefix="/audio", tags=["Admin Transcript"])


class SpeakerInfo(BaseModel):
    speaker: str
    speaker_id: Optional[int] = None
    display_name: Optional[str] = None


class SegmentItem(BaseModel):
    start: float
    end: float
    speaker: str
    text: str


class RevealedTranscript(BaseModel):
    job_id: str
    language: Optional[str] = None
    speakers: list[SpeakerInfo]
    segments: list[SegmentItem]


@router.post("/{job_id}/transcript:reveal", response_model=RevealedTranscript)
def reveal_transcript(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_user),
):
    data = crud.get_transcript_reveal_data(db, job_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Транскрипция не найдена или не готова")
    # Аудит пишется ПОСЛЕ проверки существования, но до возврата (конституция VI)
    crud.create_access_log(db, user_id=current_user.id, job_id=job_id, action="reveal")
    return data
