from fastapi import APIRouter, Query

from schemas.api.call_schema import (
    CallSearchResponse,
    CallSegmentsResponse,
)
from services.async_qdrant_service import AsyncQdrantService


router = APIRouter(
    prefix="/calls",
    tags=["Calls"]
)


@router.get(
    "/search",
    response_model=CallSearchResponse,
    summary="Search calls",
    description=(
        "Searches transcript segments using keyword, semantic or hybrid mode. "
        "If job_id is not provided, search runs globally across all processed calls."
    )
)
async def search_calls(
    query: str = Query(
        ...,
        min_length=1,
        description="Search query."
    ),
    job_id: str | None = Query(
        None,
        description="Optional job ID. If empty, search runs globally."
    ),
    speaker: str | None = Query(
        None,
        description="Optional speaker label, for example SPEAKER_00."
    ),
    mode: str = Query(
        "hybrid",
        description="Search mode: keyword, semantic or hybrid."
    ),
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of results."
    )
):
    qdrant_service = AsyncQdrantService()

    results = await qdrant_service.search(
        query=query,
        job_id=job_id,
        speaker=speaker,
        mode=mode,
        limit=limit
    )

    return {
        "query": query,
        "job_id": job_id,
        "speaker": speaker,
        "mode": mode,
        "limit": limit,
        "count": len(results),
        "results": results
    }


@router.get(
    "/{job_id}",
    response_model=CallSegmentsResponse,
    summary="Get call by job ID",
    description="Returns transcript segments indexed for one processed call."
)
async def get_call_by_job_id(job_id: str):
    qdrant_service = AsyncQdrantService()

    segments = await qdrant_service.get_segments_by_job(
        job_id
    )

    return {
        "job_id": job_id,
        "count": len(segments),
        "segments": segments
    }