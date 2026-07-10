from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import get_db
from api.auth_users import get_current_user
from call_agent.config import get_settings
from call_agent.summary import summarize_transcript
from database import crud
from database.models import Transcript

router = APIRouter(prefix="/calls", tags=["Admin Calls"])


def _transcript_text(db: Session, job_id: str) -> str | None:
    row = db.query(Transcript).filter(Transcript.job_id == job_id).first()
    return row.full_text if row else None


@router.get("")
def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verdict: Optional[str] = Query(None),
    scenario: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return crud.list_calls(db, page=page, page_size=page_size, verdict=verdict,
                           scenario=scenario, date_from=date_from, date_to=date_to)


@router.get("/{call_id}")
def get_call(call_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    detail = crud.get_call_detail(db, call_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Звонок не найден")
    return detail


@router.post("/{call_id}/summary")
def regenerate_summary(call_id: str, db: Session = Depends(get_db),
                       _user=Depends(get_current_user)):
    detail = crud.get_call_detail(db, call_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Звонок не найден")
    job_id = detail["call"].get("job_id")
    text = _transcript_text(db, job_id) if job_id else None
    if not text:
        raise HTTPException(status_code=409, detail="Транскрипция ещё не готова")
    summary = summarize_transcript(text, get_settings())
    if summary is None:
        raise HTTPException(status_code=502, detail="Сервис выжимки недоступен")
    crud.set_call_summary(db, call_id, summary)
    return {"summary": summary}
