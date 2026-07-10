from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import get_db
from api.auth_users import get_current_user
from database import crud

router = APIRouter(prefix="/analytics", tags=["Admin Analytics"])


class AnalyticsSummary(BaseModel):
    total_audio: int
    total_transcribed: int
    by_status: dict[str, int]


class WordCount(BaseModel):
    word: str
    count: int


class SpeakerCount(BaseModel):
    speaker_id: int
    name: str
    count: int


class TimeBucket(BaseModel):
    bucket: datetime
    count: int


@router.get("/summary", response_model=AnalyticsSummary)
def get_summary(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return crud.analytics_summary(db)


@router.get("/frequent-words", response_model=list[WordCount])
def get_frequent_words(
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return crud.frequent_words(db, limit=limit)


@router.get("/frequent-speakers", response_model=list[SpeakerCount])
def get_frequent_speakers(
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return crud.frequent_speakers(db, limit=limit)


@router.get("/uploads-over-time", response_model=list[TimeBucket])
def get_uploads_over_time(
    bucket: Literal["hour", "day"] = Query("day"),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return crud.uploads_over_time(db, bucket=bucket)
