from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import get_db
from api.auth_users import require_role
from database import crud

router = APIRouter(prefix="/audit-log", tags=["Admin Audit"])

_super_admin = require_role("super_admin")


class AuditLogItem(BaseModel):
    id: int
    user_id: int
    user_login: str
    job_id: str
    action: str
    created_at: datetime


class AuditLogPage(BaseModel):
    items: list[AuditLogItem]
    page: int
    page_size: int
    total: int
    pages: int


@router.get("", response_model=AuditLogPage)
def list_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(_super_admin),
):
    return crud.list_access_log(
        db,
        page=page,
        page_size=page_size,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
    )
