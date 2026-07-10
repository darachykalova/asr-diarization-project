from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from api.auth import get_db
from api.auth_users import get_current_user, hash_password, require_role
from database import crud

router = APIRouter(prefix="/users", tags=["Admin Users"])

_super_admin = require_role("super_admin")


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    login: str
    role: str
    is_blocked: bool
    created_at: datetime


class CreateUserRequest(BaseModel):
    login: str
    password: str = Field(min_length=8)
    role: Literal["moderator", "super_admin"] = "moderator"


class PatchUserRequest(BaseModel):
    role: Optional[Literal["moderator", "super_admin"]] = None
    is_blocked: Optional[bool] = None


@router.get("", response_model=list[UserPublic])
def list_users(
    db: Session = Depends(get_db),
    _user=Depends(_super_admin),
):
    return crud.list_admin_users(db)


@router.post("", response_model=UserPublic, status_code=201)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    _user=Depends(_super_admin),
):
    if crud.get_admin_user_by_login(db, body.login):
        raise HTTPException(status_code=409, detail="Пользователь с таким логином уже существует")
    return crud.create_admin_user(db, body.login, hash_password(body.password), body.role)


@router.patch("/{user_id}", response_model=UserPublic)
def patch_user(
    user_id: int,
    body: PatchUserRequest,
    db: Session = Depends(get_db),
    _user=Depends(_super_admin),
):
    try:
        if body.role is not None:
            user = crud.update_admin_user_role(db, user_id, body.role)
            if user is None:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
        if body.is_blocked is not None:
            user = crud.set_admin_user_blocked(db, user_id, body.is_blocked)
            if user is None:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # Вернуть актуальное состояние если ни одно поле не менялось
    result = crud.get_admin_user_by_id(db, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return result
