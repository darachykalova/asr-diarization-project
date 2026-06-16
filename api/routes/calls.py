from enum import Enum
from math import ceil

from fastapi import APIRouter, Depends, Query
from starlette.concurrency import run_in_threadpool

from api.auth import require_scope
from database.repository import TranscriptRepository
from schemas.api.call_schema import (
    CallSearchResponse,
    CallSegmentsResponse,
)
from services.async_qdrant_service import AsyncQdrantService
from services.reindex_service import ReindexService


class SearchMode(str, Enum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"


router = APIRouter(
    prefix="/calls",
    tags=["Calls"]
)


@router.get(
    "/search",
    response_model=CallSearchResponse,
    summary="Search calls",
    description=(
        "Keyword search uses Postgres. "
        "Semantic search uses Qdrant."
    ),
    dependencies=[Depends(require_scope("read"))]
)
async def search_calls(
    query: str = Query(..., min_length=1),
    job_id: str | None = Query(None),
    speaker: str | None = Query(None),
    mode: SearchMode = Query(...),
    limit: int = Query(10, ge=1, le=100)
):
    repository = TranscriptRepository()

    if mode == SearchMode.KEYWORD:
        results = await run_in_threadpool(
            repository.keyword_search,
            query,
            job_id,
            speaker,
            limit
        )
    else:
        qdrant_service = AsyncQdrantService()

        results = await qdrant_service.search(
            query=query,
            job_id=job_id.strip() if job_id else None,
            speaker=speaker.strip() if speaker else None,
            mode=mode.value,
            limit=limit
        )

    return {
        "query": query,
        "job_id": job_id.strip() if job_id else None,
        "speaker": speaker.strip() if speaker else None,
        "mode": mode.value,
        "limit": limit,
        "count": len(results),
        "results": results
    }


def _get_call_segments_from_postgres(job_id: str) -> list[dict]:
    repository = TranscriptRepository()

    return repository.get_call_segments_by_job_id(
        job_id=job_id
    )


@router.get(
    "/{job_id}",
    response_model=CallSegmentsResponse,
    summary="Get call by job ID",
    description="Returns transcript segments from Postgres for one processed call.",
    dependencies=[Depends(require_scope("read"))]
)
async def get_call_by_job_id(
    job_id: str,
    speaker: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100)
):
    all_segments = await run_in_threadpool(
        _get_call_segments_from_postgres,
        job_id
    )

    clean_speaker = speaker.strip() if speaker else None

    if clean_speaker:
        all_segments = [
            segment
            for segment in all_segments
            if segment.get("speaker") == clean_speaker
        ]

    total = len(all_segments)
    pages = ceil(total / page_size) if total else 0
    offset = (page - 1) * page_size

    paginated_segments = all_segments[
        offset:offset + page_size
    ]

    return {
        "job_id": job_id.strip(),
        "count": len(paginated_segments),
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
        "segments": paginated_segments
    }


def _reindex_call_to_qdrant(job_id: str) -> dict:
    service = ReindexService()

    return service.reindex_job(
        job_id=job_id
    )


@router.post(
    "/reindex/{job_id}",
    summary="Reindex call to Qdrant",
    description="Loads transcript segments from Postgres and saves them to Qdrant for semantic search.",
    dependencies=[Depends(require_scope("write"))]
)
async def reindex_call(job_id: str):
    return await run_in_threadpool(
        _reindex_call_to_qdrant,
        job_id
    )