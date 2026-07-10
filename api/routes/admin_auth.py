from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from api.auth import get_db
from api.auth_users import create_token, get_current_user, verify_password
from api.limiter import limiter
from database.crud import get_admin_user_by_login
from database.models import AdminUser

router = APIRouter(prefix="/auth", tags=["Admin Auth"])


class LoginRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    role: str
    is_blocked: bool
    created_at: datetime


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute", key_func=get_remote_address)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = get_admin_user_by_login(db, body.login)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.is_blocked:
        raise HTTPException(status_code=401, detail="Account blocked")
    token = create_token(user.id, user.role)
    return TokenResponse(access_token=token, role=user.role)


@router.get("/me", response_model=UserPublic)
def me(current_user: AdminUser = Depends(get_current_user)):
    return current_user
