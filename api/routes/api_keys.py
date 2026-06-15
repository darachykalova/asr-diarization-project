import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import get_db, require_scope
from database.models import ApiKey


router = APIRouter(
    prefix="/api-keys",
    tags=["API Keys"]
)


class ApiKeyCreate(BaseModel):
    scopes: str = "read,write"
    rate_limit: int = 100


class ApiKeyResponse(BaseModel):
    id: int
    scopes: str
    rate_limit: int
    created_at: datetime
    revoked_at: datetime | None

    model_config = {
        "from_attributes": True
    }


class ApiKeyCreatedResponse(ApiKeyResponse):
    raw_key: str


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    summary="Create API key",
    description="Creates a new API key. Raw key is shown only once."
)
def create_api_key(
    data: ApiKeyCreate,
    db: Session = Depends(get_db),
    _: ApiKey = Depends(require_scope("admin"))
):
    raw_key = secrets.token_urlsafe(32)

    key_hash = hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()

    api_key = ApiKey(
        key_hash=key_hash,
        scopes=data.scopes,
        rate_limit=data.rate_limit
    )

    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return {
        "id": api_key.id,
        "scopes": api_key.scopes,
        "rate_limit": api_key.rate_limit,
        "created_at": api_key.created_at,
        "revoked_at": api_key.revoked_at,
        "raw_key": raw_key
    }


@router.get(
    "",
    response_model=list[ApiKeyResponse],
    summary="List API keys"
)
def list_api_keys(
    db: Session = Depends(get_db),
    _: ApiKey = Depends(require_scope("admin"))
):
    return (
        db.query(ApiKey)
        .order_by(ApiKey.id)
        .all()
    )


@router.delete(
    "/{key_id}",
    summary="Revoke API key"
)
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    _: ApiKey = Depends(require_scope("admin"))
):
    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id)
        .first()
    )

    if api_key is None:
        raise HTTPException(
            status_code=404,
            detail="API key not found"
        )

    if api_key.revoked_at is not None:
        raise HTTPException(
            status_code=400,
            detail="API key already revoked"
        )

    api_key.revoked_at = datetime.utcnow()
    db.commit()

    return {
        "message": f"API key {key_id} revoked"
    }