from celery.result import AsyncResult
from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from celery_app import celery_app
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


router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


def _build_job_status_response(
    job_id: str
) -> dict:
    task_result = AsyncResult(
        job_id,
        app=celery_app
    )

    celery_state = task_result.state

    response = {
        "job_id": job_id,
        "status": CELERY_STATUS_MAP.get(
            celery_state,
            celery_state
        ),
        "error": None
    }

    if task_result.failed():
        response["error"] = str(task_result.result)

    return response


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Returns simplified processing status for a background task."
)
async def get_job_status(job_id: str):
    return await run_in_threadpool(
        _build_job_status_response,
        job_id
    )