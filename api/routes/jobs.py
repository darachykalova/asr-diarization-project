from celery.result import AsyncResult
from fastapi import APIRouter, Query

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


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description="Returns task status directly from Celery backend."
)
def get_job_status(
    job_id: str,
    include_result: bool = Query(
        False,
        description="Whether to include task result when task is finished."
    )
):
    task_result = AsyncResult(
        job_id,
        app=celery_app
    )

    celery_state = task_result.state

    response = {
        "job_id": job_id,
        "celery_state": celery_state,
        "status": CELERY_STATUS_MAP.get(
            celery_state,
            celery_state
        ),
        "ready": task_result.ready(),
        "successful": task_result.successful(),
        "failed": task_result.failed()
    }

    if task_result.failed():
        response["error"] = str(task_result.result)
        response["traceback"] = task_result.traceback

    if include_result and task_result.ready() and not task_result.failed():
        response["result"] = task_result.result

    return response