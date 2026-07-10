import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.concurrency import run_in_threadpool

from api.limiter import limiter
from api.routes import api_router
from api.routes.health import router as health_router
from database.init_db import init_db
from services.logging_json import setup_json_logging

setup_json_logging()

_bearer = HTTPBearer(auto_error=False)

app = FastAPI(
    title="Audio Intelligence API",
    description=(
        "API for asynchronous audio transcription, "
        "speaker diarization and transcript search."
    ),
    version="1.0.0",
    docs_url=None,   # served locally below — no CDN required
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory="api/static"), name="static")


@app.get("/docs", include_in_schema=False)
async def swagger_ui_html() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " — Swagger UI",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_html() -> HTMLResponse:
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " — ReDoc",
        redoc_js_url="/static/redoc.standalone.js",
    )

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS для фронтенда. В prod задайте CORS_ORIGINS через env (список через запятую).
# В dev Vite-прокси обходит CORS, поэтому этот middleware нужен только для прод.
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def _bootstrap_admin() -> None:
    login = os.getenv("ADMIN_BOOTSTRAP_LOGIN")
    password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
    if not login or not password:
        return
    from database.models import AdminUser
    from database.session import SessionLocal
    from database.crud import create_admin_user
    from api.auth_users import hash_password
    db = SessionLocal()
    try:
        if db.query(AdminUser).count() == 0:
            create_admin_user(db, login, hash_password(password), role="super_admin")
            logging.getLogger(__name__).info("Bootstrap super-admin created: %s", login)
    finally:
        db.close()


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

    logger.info("Bootstrapping first admin user if needed...")
    await run_in_threadpool(_bootstrap_admin)
    logger.info("Admin bootstrap check done.")

    logger.info("Seeding default platform settings...")
    from database.session import SessionLocal as _SL
    from database.crud import seed_default_settings as _seed, cleanup_old_audit_logs as _cleanup
    _db = _SL()
    try:
        _seed(_db)
        deleted = _cleanup(_db)
        if deleted:
            logger.info("Audit log cleanup: removed %d old entries.", deleted)
    finally:
        _db.close()
    logger.info("Platform settings seeded.")

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
