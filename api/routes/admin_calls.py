from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.auth import get_db
from api.auth_users import get_current_user
from database import crud

router = APIRouter(prefix="/calls", tags=["Admin Calls"])


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
