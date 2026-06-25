import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.concurrency import run_in_threadpool

from api.routes import api_router
from api.routes.health import router as health_router
from database.init_db import init_db
from services.logging_json import setup_json_logging

setup_json_logging()

_DEFAULT_RATE = os.getenv("API_RATE_LIMIT", "60/minute")
_bearer = HTTPBearer(auto_error=False)


def _key_by_api_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()[:64]  # use token as key, truncated for safety
    return request.client.host if request.client else "anonymous"


limiter = Limiter(key_func=_key_by_api_key, default_limits=[_DEFAULT_RATE])

app = FastAPI(
    title="Audio Intelligence API",
    description=(
        "API for asynchronous audio transcription, "
        "speaker diarization and transcript search."
    ),
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

_audit_logger = logging.getLogger("audit")


@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    response = await call_next(request)
    api_key_id = getattr(request.state, "api_key_id", None)
    _audit_logger.info(
        "access",
        extra={
            "job_id": None,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ip": request.client.host if request.client else None,
            "api_key_id": api_key_id,
        },
    )
    return response


@app.on_event("startup")
async def startup():
    logger = logging.getLogger(__name__)

    # Pre-flight: refuse to start if required ML models are missing locally
    # (offline mode — Hugging Face is never contacted at runtime).
    from services.model_registry import ensure_available
    logger.info("Verifying required ML models are present locally...")
    ensure_available()
    logger.info("All required ML models present.")

    logger.info("Initializing database tables...")
    await run_in_threadpool(init_db)
    logger.info("Database tables initialized.")

    from services.text_embedding_service import TextEmbeddingService
    from clients.minio_client import MinioStorageClient

    logger.info("Preloading SentenceTransformer model...")
    await run_in_threadpool(TextEmbeddingService)
    logger.info("SentenceTransformer model loaded.")

    logger.info("Checking MinIO bucket...")
    await run_in_threadpool(MinioStorageClient)
    logger.info("MinIO bucket ready.")


app.include_router(health_router)
app.include_router(api_router)