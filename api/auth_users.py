import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database.models import AdminUser
from database.session import SessionLocal

_JWT_SECRET = os.getenv("ADMIN_JWT_SECRET", "")
_JWT_ALGORITHM = "HS256"
_JWT_TTL_HOURS = int(os.getenv("ADMIN_JWT_TTL_HOURS", "8"))

_security = HTTPBearer(auto_error=False)


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_JWT_TTL_HOURS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
    db: Session = Depends(_get_db),
) -> AdminUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization header required")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(AdminUser).filter(AdminUser.id == int(payload["sub"])).first()
    if user is None or user.is_blocked:
        raise HTTPException(status_code=401, detail="User not found or blocked")
    return user


def require_role(role: str):
    def _check(user: AdminUser = Depends(get_current_user)) -> AdminUser:
        if user.role != role:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role}' required, got '{user.role}'",
            )
        return user

    return _check
