import os
import hashlib
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)


class QdrantService:
    COLLECTION_NAME = "transcript_segments"
    VECTOR_SIZE = 384

    def __init__(self, host: str | None = None, port: int | None = None):
        """
        Инициализация Qdrant клиента.
        В Docker можно использовать QDRANT_HOST=qdrant, QDRANT_PORT=6333
        """
        host = host or os.getenv("QDRANT_HOST", "localhost")
        port = port or int(os.getenv("QDRANT_PORT", 6333))

        self.client = QdrantClient(
            host=host,
            port=port
        )

    def health_check(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def ensure_collection(self) -> bool:
        try:
            collections = self.client.get_collections()

            existing = {collection.name for collection in collections.collections}

            if self.COLLECTION_NAME not in existing:
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE
                    )
                )

            return True

        except Exception as error:
            print(f"Qdrant collection error: {error}")
            return False

    def save_segments(self, job_id: str, segments: list) -> bool:
        try:
            if not self.ensure_collection():
                return False

            points = []

            for segment in segments:
                text = segment.text.strip()
                if not text:
                    continue

                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{job_id}_{segment.id}"))
                vector = self._build_text_vector_safely(text)

                payload = {
                    "job_id": job_id,
                    "segment_id": segment.id,
                    "speaker": segment.speaker,
                    "start": segment.start,
                    "end": segment.end,
                    "text": text,
                    "overlap": segment.overlap,
                    "alignment_source": segment.alignment_source,
                    "embedding_source": self._get_embedding_source(vector)
                }

                points.append(PointStruct(id=point_id, vector=vector, payload=payload))

            if not points:
                return False

            self.client.upsert(collection_name=self.COLLECTION_NAME, points=points)

            return True

        except Exception as error:
            print(f"Qdrant save segments error: {error}")
            return False

    def get_segments_by_job_id(self, job_id: str) -> list[dict]:
        try:
            qdrant_filter = Filter(
                must=[FieldCondition(key="job_id", match=MatchValue(value=job_id))]
            )

            points, _ = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=qdrant_filter,
                limit=1000,
                with_payload=True,
                with_vectors=False
            )

            segments = [point.payload for point in points if point.payload is not None]
            segments.sort(key=lambda item: item.get("start", 0))
            return segments

        except Exception as error:
            print(f"Qdrant get segments error: {error}")
            return []

    def search_segments_by_text(self, query: str, job_id: str | None = None) -> list[dict]:
        try:
            points, _ = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                limit=1000,
                with_payload=True,
                with_vectors=False
            )

            query_lower = query.lower().strip()
            results = []

            for point in points:
                payload = point.payload
                if payload is None:
                    continue

                text = payload.get("text", "")
                if job_id is not None and payload.get("job_id") != job_id:
                    continue

                if query_lower in text.lower():
                    results.append(payload)

            results.sort(key=lambda item: item.get("start", 0))
            return results

        except Exception as error:
            print(f"Qdrant text search error: {error}")
            return []

    # вспомогательные методы для безопасной генерации векторов
    def _build_text_vector_safely(self, text: str) -> list[float]:
        try:
            from services.text_embedding_service import TextEmbeddingService
            service = TextEmbeddingService()
            vector = service.embed_text(text)

            if len(vector) == self.VECTOR_SIZE:
                return vector

            print(f"Embedding vector size mismatch: expected {self.VECTOR_SIZE}, got {len(vector)}")
            return self._build_placeholder_vector(text)

        except Exception as error:
            print(f"Text embedding failed, using placeholder: {error}")
            return self._build_placeholder_vector(text)

    def _get_embedding_source(self, vector: list[float]) -> str:
        return "text_embedding_or_placeholder" if len(vector) == self.VECTOR_SIZE else "unknown"

    def _build_placeholder_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = [(digest[i % len(digest)] / 255.0) * 2.0 - 1.0 for i in range(self.VECTOR_SIZE)]
        return vector