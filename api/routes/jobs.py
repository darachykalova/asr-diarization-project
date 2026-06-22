from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from api.auth import require_scope
from celery_app.app import celery_app
from database import crud
from database.session import SessionLocal
from schemas.api.job_schema import JobStatusResponse


CELERY_STATUS_MAP = {
    "PENDING": "queued",
    "RECEIVED": "queued",
    "STARTED": "processing",
    "SUCCESS": "done",
    "FAILURE": "failed",
    "RETRY": "retrying",
    "REVOKED": "revoked",
}

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _build_job_status_response(job_id: str) -> dict:
    db = SessionLocal()
    try:
        job = crud.get_job_by_id(db=db, job_id=job_id)
    finally:
        db.close()

    if job is not None:
        return {
            "job_id": job.id,
            "status": job.status,
            "progress": job.progress,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
        }

    # Fallback: check Celery only if task is actively tracked (non-PENDING state)
    task_result = AsyncResult(job_id, app=celery_app)
    celery_state = task_result.state

    # PENDING is Celery's default for unknown tasks — treat as not found
    if celery_state == "PENDING":
        raise HTTPException(status_code=404, detail="Job not found")

    error = str(task_result.result) if task_result.failed() else None

    return {
        "job_id": job_id,
        "status": CELERY_STATUS_MAP.get(celery_state, celery_state.lower()),
        "progress": 0,
        "error_code": None,
        "error_message": error,
        "created_at": None,
        "started_at": None,
        "finished_at": None,
    }


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Returns job status and progress. Reads from Postgres; falls back to Celery if not yet persisted.",
    dependencies=[Depends(require_scope("read"))]
)
async def get_job_status(job_id: str):
    return await run_in_threadpool(_build_job_status_response, job_id)
