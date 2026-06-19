import logging
import os
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

logger = logging.getLogger(__name__)


class SpeakerIdentificationService:
    COLLECTION_NAME = "speaker_voices"
    VECTOR_SIZE = 192
    MATCH_THRESHOLD = float(os.getenv("SPEAKER_MATCH_THRESHOLD", "0.80"))

    def __init__(self):
        self.client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333"))
        )
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        collections = self.client.get_collections()
        existing = {c.name for c in collections.collections}

        if self.COLLECTION_NAME in existing:
            info = self.client.get_collection(self.COLLECTION_NAME)
            existing_size = info.config.params.vectors.size
            if existing_size == self.VECTOR_SIZE:
                return
            logger.info(
                "Qdrant collection '%s' has vector size %s, expected %s. Recreating.",
                self.COLLECTION_NAME,
                existing_size,
                self.VECTOR_SIZE
            )
            self.client.delete_collection(self.COLLECTION_NAME)

        self.client.create_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=self.VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )

    def find_speaker(
        self,
        embedding: list[float],
        excluded_speaker_ids: set[int] | None = None
    ) -> tuple[int | None, float | None]:
        if excluded_speaker_ids is None:
            excluded_speaker_ids = set()

        result = self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=embedding,
            limit=5,
            with_payload=True,
            with_vectors=False
        )

        if not result.points:
            return None, None

        best_score = None

        for point in result.points:
            score = float(point.score)
            best_score = score if best_score is None else max(best_score, score)

            payload = point.payload or {}
            speaker_id = payload.get("speaker_id")

            if speaker_id is None:
                continue

            speaker_id = int(speaker_id)

            if speaker_id in excluded_speaker_ids:
                continue

            if score >= self.MATCH_THRESHOLD:
                return speaker_id, score

        return None, best_score

    def save_embedding(
        self,
        speaker_id: int,
        embedding: list[float]
    ) -> None:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"speaker_{speaker_id}"))
        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={"speaker_id": speaker_id}
                )
            ]
        )

    def delete_speaker(
        self,
        speaker_id: int
    ) -> None:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"speaker_{speaker_id}"))
        self.client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=[point_id]
        )
