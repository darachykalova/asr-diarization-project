from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from api.auth import require_scope
from services.qdrant_service import QdrantService

router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "",
    summary="Search transcript segments",
    description=(
        "Semantic, keyword, or hybrid search over all transcript segments. "
        "Pass `job_id` to scope results to a single transcription."
    ),
    dependencies=[Depends(require_scope("read"))],
)
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    mode: str = Query("hybrid", description="Search mode: semantic | keyword | hybrid"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    speaker: Optional[str] = Query(None, description="Filter by speaker label"),
    limit: int = Query(10, ge=1, le=100, description="Max results to return"),
):
    if mode not in {"semantic", "keyword", "hybrid"}:
        raise HTTPException(
            status_code=422,
            detail="mode must be one of: semantic, keyword, hybrid",
        )

    results = await run_in_threadpool(
        QdrantService().search,
        query=q,
        job_id=job_id,
        speaker=speaker,
        mode=mode,
        limit=limit,
    )

    return {"query": q, "mode": mode, "total": len(results), "items": results}
