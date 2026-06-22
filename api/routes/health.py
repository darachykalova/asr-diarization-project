import os

import redis as redis_lib
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from database.session import SessionLocal


router = APIRouter(tags=["Health"])


@router.get("/healthz", summary="Liveness check")
async def healthz():
    return {"status": "ok", "service": "Audio Intelligence API"}


@router.get("/readyz", summary="Readiness check")
async def readyz():
    errors = {}

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as exc:
        errors["postgres"] = str(exc)

    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis_lib.from_url(redis_url, socket_connect_timeout=2)
        r.ping()
    except Exception as exc:
        errors["redis"] = str(exc)

    if errors:
        return JSONResponse(status_code=503, content={"status": "not ready", "errors": errors})

    return {"status": "ready"}


@router.get("/", response_model=dict, summary="Health check")
async def health_check():
    return {"status": "ok", "service": "Audio Intelligence API"}
