from types import SimpleNamespace

from database.repository import TranscriptRepository
from services.qdrant_service import QdrantService


class ReindexService:
    """
    Reindexes transcript segments from Postgres to Qdrant.
    """

    def __init__(self):
        self.repository = TranscriptRepository()
        self.qdrant_service = QdrantService()

    def reindex_job(self, job_id: str) -> dict:
        clean_job_id = job_id.strip()

        segments = self.repository.get_call_segments_by_job_id(
            job_id=clean_job_id
        )

        if not segments:
            return {
                "job_id": clean_job_id,
                "status": "not_found",
                "segments_count": 0,
                "saved_to_qdrant": False
            }

        qdrant_segments = []

        for segment in segments:
            qdrant_segments.append(
                SimpleNamespace(
                    id=segment["segment_id"],
                    start=segment["start"],
                    end=segment["end"],
                    speaker=segment["speaker"],
                    text=segment["text"],
                    overlap=False,
                    alignment_source=segment.get("alignment_source") or "postgres",
                    diarization_source=segment.get("diarization_source") or "postgres"
                )
            )

        saved = self.qdrant_service.save_segments(
            job_id=clean_job_id,
            segments=qdrant_segments
        )

        return {
            "job_id": clean_job_id,
            "status": "done" if saved else "failed",
            "segments_count": len(qdrant_segments),
            "saved_to_qdrant": saved
        }