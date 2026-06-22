import hashlib
import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database.models import ApiKey
from database.session import SessionLocal


logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()


def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> ApiKey:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required. Use: Authorization: Bearer <api_key>"
        )

    key_hash = hash_key(
        credentials.credentials
    )

    api_key = (
        db.query(ApiKey)
        .filter(
            ApiKey.key_hash == key_hash,
            ApiKey.revoked_at.is_(None)
        )
        .first()
    )

    if api_key is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or revoked API key"
        )

    logger.debug(
        "API key verified: id=%s scopes=%s",
        api_key.id,
        api_key.scopes
    )

    request.state.api_key_id = api_key.id
    return api_key


def require_scope(scope: str):
    def _check_scope(
        api_key: ApiKey = Depends(verify_api_key)
    ) -> ApiKey:
        allowed_scopes = [
            item.strip()
            for item in api_key.scopes.split(",")
        ]

        if "admin" in allowed_scopes:
            return api_key

        if scope not in allowed_scopes:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"This action requires scope: '{scope}'. "
                    f"Your key has: {api_key.scopes}"
                )
            )

        return api_key

    return _check_scope