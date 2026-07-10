from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import get_db
from api.auth_users import get_current_user, require_role
from database import crud
from database.models import AdminUser

router = APIRouter(prefix="/settings", tags=["Admin Settings"])

_super_admin = require_role("super_admin")


class SettingOut(BaseModel):
    key: str
    value: str
    value_type: str
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    key: str
    value: str


@router.get("", response_model=list[SettingOut])
def get_settings(
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(_super_admin),
):
    return crud.get_all_settings(db)


@router.put("", response_model=list[SettingOut])
def update_settings(
    body: list[SettingUpdate],
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(_super_admin),
):
    try:
        return crud.upsert_settings(
            db,
            [u.model_dump() for u in body],
            updated_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
