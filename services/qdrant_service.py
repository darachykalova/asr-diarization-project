import hashlib
import logging
import os
import re
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)


logger = logging.getLogger(__name__)


class QdrantService:
    COLLECTION_NAME = "transcript_segments"
    VECTOR_SIZE = 384

    DEFAULT_LIMIT = 10
    MIN_SEMANTIC_SCORE = 0.35

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None
    ):
        self.client = QdrantClient(
            host=host or os.getenv("QDRANT_HOST", "localhost"),
            port=port or int(os.getenv("QDRANT_PORT", "6333"))
        )

    def health_check(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            logger.exception("Qdrant health check failed")
            return False

    def ensure_collection(self) -> bool:
        try:
            collections = self.client.get_collections()

            existing = {
                collection.name
                for collection in collections.collections
            }

            if self.COLLECTION_NAME not in existing:
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE
                    )
                )

            return True

        except Exception:
            logger.exception("Qdrant collection initialization failed")
            return False

    def save_segments(
        self,
        job_id: str,
        segments: list
    ) -> bool:
        try:
            if not self.ensure_collection():
                return False

            embedding_service = self._create_embedding_service_safely()
            points = []

            for segment in segments:
                text = segment.text.strip()

                if not text:
                    continue

                point_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_DNS,
                        f"{job_id}_{segment.id}"
                    )
                )

                embedding_text = self._build_embedding_text(
                    speaker=segment.speaker,
                    text=text
                )

                vector, embedding_source = self._build_text_vector_safely(
                    text=embedding_text,
                    embedding_service=embedding_service
                )

                payload = {
                    "job_id": job_id,
                    "segment_id": segment.id,
                    "speaker": segment.speaker,
                    "start": segment.start,
                    "end": segment.end,
                    "text": text,
                    "embedding_text": embedding_text,
                    "overlap": segment.overlap,
                    "alignment_source": segment.alignment_source,
                    "diarization_source": segment.diarization_source,
                    "embedding_source": embedding_source
                }

                points.append(
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    )
                )

            if not points:
                logger.warning(
                    "No transcript segments to save for job %s",
                    job_id
                )
                return False

            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=points
            )

            return True

        except Exception:
            logger.exception(
                "Qdrant save segments failed for job %s",
                job_id
            )
            return False

    def get_segments_by_job_id(
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

            points, _ = self.client.scroll(
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
                "Qdrant get segments failed for job %s",
                job_id
            )
            return []

    def get_segments_by_job(
        self,
        job_id: str
    ) -> list[dict]:
        return self.get_segments_by_job_id(job_id)

    def search(
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
            return self.keyword_search(
                query=query,
                job_id=job_id,
                speaker=speaker,
                limit=limit
            )

        if normalized_mode == "semantic":
            return self.semantic_search(
                query=query,
                job_id=job_id,
                speaker=speaker,
                limit=limit
            )

        return self.hybrid_search(
            query=query,
            job_id=job_id,
            speaker=speaker,
            limit=limit
        )

    def keyword_search(
        self,
        query: str,
        job_id: str | None = None,
        speaker: str | None = None,
        limit: int = DEFAULT_LIMIT
    ) -> list[dict]:
        try:
            points, _ = self.client.scroll(
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

                result = self._build_result_item(
                    payload=payload,
                    score=round(score, 4),
                    score_type="keyword"
                )

                results.append(result)

            results.sort(
                key=lambda item: item["score"],
                reverse=True
            )

            return results[:limit]

        except Exception:
            logger.exception("Qdrant keyword search failed")
            return []

    def semantic_search(
        self,
        query: str,
        job_id: str | None = None,
        speaker: str | None = None,
        limit: int = DEFAULT_LIMIT
    ) -> list[dict]:
        try:
            embedding_service = self._create_embedding_service_safely()

            if embedding_service is None:
                return []

            query_vector = embedding_service.embed_text(query)

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

            query_result = self.client.query_points(
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

                result = self._build_result_item(
                    payload=payload,
                    score=round(semantic_score, 4),
                    score_type="semantic"
                )

                results.append(result)

            results.sort(
                key=lambda item: item["score"],
                reverse=True
            )

            return results[:limit]

        except Exception:
            logger.exception("Qdrant semantic search failed")
            return []

    def hybrid_search(
        self,
        query: str,
        job_id: str | None = None,
        speaker: str | None = None,
        limit: int = DEFAULT_LIMIT
    ) -> list[dict]:
        keyword_results = self.keyword_search(
            query=query,
            job_id=job_id,
            speaker=speaker,
            limit=50
        )

        semantic_results = self.semantic_search(
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

    def search_text(
        self,
        query: str,
        job_id: str | None = None
    ) -> list[dict]:
        return self.keyword_search(
            query=query,
            job_id=job_id
        )

    def search_segments_by_text(
        self,
        query: str,
        job_id: str | None = None
    ) -> list[dict]:
        return self.keyword_search(
            query=query,
            job_id=job_id
        )

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

    def _build_embedding_text(
        self,
        speaker: str,
        text: str
    ) -> str:
        return f"{speaker}: {text}"

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

    def _create_embedding_service_safely(self):
        try:
            from services.text_embedding_service import TextEmbeddingService

            return TextEmbeddingService()

        except Exception as error:
            logger.warning(
                "TextEmbeddingService init failed: %s",
                error
            )
            return None

    def _build_text_vector_safely(
        self,
        text: str,
        embedding_service
    ) -> tuple[list[float], str]:
        if embedding_service is None:
            return (
                self._build_placeholder_vector(text),
                "placeholder"
            )

        try:
            vector = embedding_service.embed_text(text)

            if len(vector) == self.VECTOR_SIZE:
                return (
                    vector,
                    "sentence-transformers"
                )

            logger.warning(
                "Embedding vector size mismatch: expected %s, got %s",
                self.VECTOR_SIZE,
                len(vector)
            )

            return (
                self._build_placeholder_vector(text),
                "placeholder"
            )

        except Exception as error:
            logger.warning(
                "Text embedding failed, using placeholder: %s",
                error
            )
            return (
                self._build_placeholder_vector(text),
                "placeholder"
            )

    def _build_placeholder_vector(
        self,
        text: str
    ) -> list[float]:
        digest = hashlib.sha256(
            text.encode("utf-8")
        ).digest()

        vector = []

        for index in range(self.VECTOR_SIZE):
            byte = digest[index % len(digest)]
            value = (byte / 255.0) * 2.0 - 1.0
            vector.append(value)

        return vector