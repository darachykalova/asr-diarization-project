import logging
import os
import re

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
)
from starlette.concurrency import run_in_threadpool


logger = logging.getLogger(__name__)


class AsyncQdrantService:
    COLLECTION_NAME = "transcript_segments"
    VECTOR_SIZE = 384

    DEFAULT_LIMIT = 10
    MIN_SEMANTIC_SCORE = 0.35

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None
    ):
        self.client = AsyncQdrantClient(
            host=host or os.getenv("QDRANT_HOST", "localhost"),
            port=port or int(os.getenv("QDRANT_PORT", "6333"))
        )

    async def health_check(self) -> bool:
        try:
            await self.client.get_collections()
            return True
        except Exception:
            logger.exception("Async Qdrant health check failed")
            return False

    async def get_segments_by_job(
        self,
        job_id: str
    ) -> list[dict]:
        return await self.get_segments_by_job_id(job_id)

    async def get_segments_by_job_id(
        self,
        job_id: str
    ) -> list[dict]:
        try:
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="job_id",
                        match=MatchValue(value=job_id)
                    )
                ]
            )

            points, _ = await self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=qdrant_filter,
                limit=1000,
                with_payload=True,
                with_vectors=False
            )

            segments = [
                point.payload
                for point in points
                if point.payload is not None
            ]

            segments.sort(
                key=lambda item: item.get("start", 0)
            )

            return segments

        except Exception:
            logger.exception(
                "Async Qdrant get segments failed for job %s",
                job_id
            )
            return []

    async def search(
        self,
        query: str,
        job_id: str | None = None,
        speaker: str | None = None,
        mode: str = "hybrid",
        limit: int = DEFAULT_LIMIT
    ) -> list[dict]:
        normalized_mode = mode.lower().strip()

        if normalized_mode not in {"keyword", "semantic", "hybrid"}:
            normalized_mode = "hybrid"

        if normalized_mode == "keyword":
            return await self.keyword_search(
                query=query,
                job_id=job_id,
                speaker=speaker,
                limit=limit
            )

        if normalized_mode == "semantic":
            return await self.semantic_search(
                query=query,
                job_id=job_id,
                speaker=speaker,
                limit=limit
            )

        return await self.hybrid_search(
            query=query,
            job_id=job_id,
            speaker=speaker,
            limit=limit
        )

    async def keyword_search(
        self,
        query: str,
        job_id: str | None = None,
        speaker: str | None = None,
        limit: int = DEFAULT_LIMIT
    ) -> list[dict]:
        try:
            points, _ = await self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=1000,
                with_payload=True,
                with_vectors=False
            )

            query_clean = query.lower().strip()
            query_words = self._tokenize(query_clean)

            results = []

            for point in points:
                payload = point.payload

                if payload is None:
                    continue

                if not self._payload_matches_filters(
                    payload=payload,
                    job_id=job_id,
                    speaker=speaker
                ):
                    continue

                text = payload.get("text", "")
                text_lower = text.lower()
                text_words = self._tokenize(text_lower)

                score = 0.0

                if query_clean and query_clean in text_lower:
                    score += 1.0

                if query_words:
                    matched_words = query_words.intersection(text_words)
                    score += len(matched_words) / len(query_words)

                if score <= 0:
                    continue

                results.append(
                    self._build_result_item(
                        payload=payload,
                        score=round(score, 4),
                        score_type="keyword"
                    )
                )

            results.sort(
                key=lambda item: item["score"],
                reverse=True
            )

            return results[:limit]

        except Exception:
            logger.exception("Async Qdrant keyword search failed")
            return []

    async def semantic_search(
        self,
        query: str,
        job_id: str | None = None,
        speaker: str | None = None,
        limit: int = DEFAULT_LIMIT
    ) -> list[dict]:
        try:
            embedding_service = await self._create_embedding_service_safely()

            if embedding_service is None:
                return []

            query_vector = await run_in_threadpool(
                embedding_service.embed_text,
                query
            )

            if len(query_vector) != self.VECTOR_SIZE:
                logger.warning(
                    "Query vector size mismatch: expected %s, got %s",
                    self.VECTOR_SIZE,
                    len(query_vector)
                )
                return []

            qdrant_filter = self._build_qdrant_filter(
                job_id=job_id,
                speaker=speaker
            )

            query_result = await self.client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=query_vector,
                query_filter=qdrant_filter,
                limit=max(limit, 20),
                with_payload=True,
                with_vectors=False
            )

            results = []

            for point in query_result.points:
                payload = point.payload or {}
                semantic_score = float(point.score)

                if semantic_score < self.MIN_SEMANTIC_SCORE:
                    continue

                results.append(
                    self._build_result_item(
                        payload=payload,
                        score=round(semantic_score, 4),
                        score_type="semantic"
                    )
                )

            results.sort(
                key=lambda item: item["score"],
                reverse=True
            )

            return results[:limit]

        except Exception:
            logger.exception("Async Qdrant semantic search failed")
            return []

    async def hybrid_search(
        self,
        query: str,
        job_id: str | None = None,
        speaker: str | None = None,
        limit: int = DEFAULT_LIMIT
    ) -> list[dict]:
        keyword_results = await self.keyword_search(
            query=query,
            job_id=job_id,
            speaker=speaker,
            limit=50
        )

        semantic_results = await self.semantic_search(
            query=query,
            job_id=job_id,
            speaker=speaker,
            limit=50
        )

        merged = {}

        for item in semantic_results:
            key = self._result_key(item)
            merged[key] = item
            merged[key]["keyword_score"] = 0.0
            merged[key]["semantic_score"] = item["score"]

        for item in keyword_results:
            key = self._result_key(item)

            if key not in merged:
                merged[key] = item
                merged[key]["semantic_score"] = 0.0
                merged[key]["keyword_score"] = item["score"]
            else:
                merged[key]["keyword_score"] = item["score"]

        query_clean = query.lower().strip()
        query_words = self._tokenize(query_clean)

        final_results = []

        for item in merged.values():
            text = item.get("text", "")
            text_lower = text.lower()
            text_words = self._tokenize(text_lower)

            semantic_score = float(item.get("semantic_score", 0.0))
            keyword_score = float(item.get("keyword_score", 0.0))

            exact_phrase_bonus = 0.0
            word_match_bonus = 0.0

            if query_clean and query_clean in text_lower:
                exact_phrase_bonus = 0.5

            if query_words:
                matched_words = query_words.intersection(text_words)
                word_match_bonus = 0.25 * (
                    len(matched_words) / len(query_words)
                )

            final_score = (
                semantic_score * 0.7
                + keyword_score * 0.8
                + exact_phrase_bonus
                + word_match_bonus
            )

            item["score"] = round(final_score, 4)
            item["score_type"] = "hybrid"
            item["semantic_score"] = round(semantic_score, 4)
            item["keyword_score"] = round(keyword_score, 4)

            final_results.append(item)

        final_results.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        return final_results[:limit]

    def _build_qdrant_filter(
        self,
        job_id: str | None = None,
        speaker: str | None = None
    ):
        conditions = []

        if job_id is not None:
            conditions.append(
                FieldCondition(
                    key="job_id",
                    match=MatchValue(value=job_id)
                )
            )

        if speaker is not None:
            conditions.append(
                FieldCondition(
                    key="speaker",
                    match=MatchValue(value=speaker)
                )
            )

        if not conditions:
            return None

        return Filter(must=conditions)

    def _payload_matches_filters(
        self,
        payload: dict,
        job_id: str | None = None,
        speaker: str | None = None
    ) -> bool:
        if job_id is not None and payload.get("job_id") != job_id:
            return False

        if speaker is not None and payload.get("speaker") != speaker:
            return False

        return True

    def _build_result_item(
        self,
        payload: dict,
        score: float,
        score_type: str
    ) -> dict:
        return {
            "score": score,
            "score_type": score_type,
            "job_id": payload.get("job_id"),
            "segment_id": payload.get("segment_id"),
            "speaker": payload.get("speaker"),
            "start": payload.get("start"),
            "end": payload.get("end"),
            "text": payload.get("text"),
            "embedding_source": payload.get("embedding_source"),
            "diarization_source": payload.get("diarization_source"),
            "alignment_source": payload.get("alignment_source"),
        }

    def _result_key(
        self,
        item: dict
    ) -> tuple:
        return (
            item.get("job_id"),
            item.get("segment_id")
        )

    def _tokenize(
        self,
        text: str
    ) -> set[str]:
        return set(
            re.findall(
                r"[a-zA-Zа-яА-ЯёЁ0-9]+",
                text.lower()
            )
        )

    async def _create_embedding_service_safely(self):
        try:
            from services.text_embedding_service import TextEmbeddingService

            return await run_in_threadpool(TextEmbeddingService)

        except Exception as error:
            logger.warning(
                "TextEmbeddingService init failed: %s",
                error
            )
            return None