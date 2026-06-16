from database.models import (
    Job,
    Recording,
    Transcript,
    TranscriptSegment,
)
from database.session import SessionLocal


class TranscriptRepository:
    """
    Repository for saving, reading and deleting transcript results from Postgres.
    """

    def save_pipeline_result(self, run_result) -> None:
        if run_result.transcript is None:
            return

        db = SessionLocal()

        try:
            existing_transcript = (
                db.query(Transcript)
                .filter(Transcript.job_id == run_result.job_id)
                .first()
            )

            if existing_transcript is not None:
                db.delete(existing_transcript)
                db.commit()

            transcript = Transcript(
                job_id=run_result.job_id,
                status=run_result.status,
                success=run_result.success,
                full_text=run_result.transcript.full_text
            )

            db.add(transcript)
            db.flush()

            for segment in run_result.transcript.segments:
                db_segment = TranscriptSegment(
                    transcript_id=transcript.id,
                    segment_id=segment.id,
                    speaker=segment.speaker,
                    start=segment.start,
                    end=segment.end,
                    text=segment.text
                )

                db.add(db_segment)

            db.commit()

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

    def get_transcript_by_job_id(self, job_id: str) -> dict | None:
        db = SessionLocal()

        try:
            clean_job_id = job_id.strip()

            transcript = (
                db.query(Transcript)
                .filter(Transcript.job_id == clean_job_id)
                .first()
            )

            if transcript is None:
                return None

            segments = (
                db.query(TranscriptSegment)
                .filter(TranscriptSegment.transcript_id == transcript.id)
                .order_by(TranscriptSegment.segment_id)
                .all()
            )

            return {
                "job_id": transcript.job_id,
                "status": transcript.status,
                "success": transcript.success,
                "transcript": {
                    "full_text": transcript.full_text,
                    "segments": [
                        {
                            "id": segment.segment_id,
                            "start": segment.start,
                            "end": segment.end,
                            "speaker": segment.speaker,
                            "text": segment.text
                        }
                        for segment in segments
                    ]
                },
                "error": None
            }

        finally:
            db.close()

    def get_call_segments_by_job_id(self, job_id: str) -> list[dict]:
        db = SessionLocal()

        try:
            clean_job_id = job_id.strip()

            transcript = (
                db.query(Transcript)
                .filter(Transcript.job_id == clean_job_id)
                .first()
            )

            if transcript is None:
                return []

            segments = (
                db.query(TranscriptSegment)
                .filter(TranscriptSegment.transcript_id == transcript.id)
                .order_by(TranscriptSegment.segment_id)
                .all()
            )

            return [
                {
                    "score": None,
                    "score_type": None,
                    "job_id": transcript.job_id,
                    "segment_id": segment.segment_id,
                    "speaker": segment.speaker,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "embedding_source": None,
                    "diarization_source": None,
                    "alignment_source": None,
                    "keyword_score": None,
                    "semantic_score": None
                }
                for segment in segments
            ]

        finally:
            db.close()

    def keyword_search(
        self,
        query: str,
        job_id: str | None = None,
        speaker: str | None = None,
        limit: int = 10
    ) -> list[dict]:
        db = SessionLocal()

        try:
            clean_query = query.strip()

            q = (
                db.query(
                    Transcript,
                    TranscriptSegment
                )
                .join(
                    TranscriptSegment,
                    Transcript.id == TranscriptSegment.transcript_id
                )
            )

            if job_id:
                q = q.filter(
                    Transcript.job_id == job_id.strip()
                )

            if speaker:
                q = q.filter(
                    TranscriptSegment.speaker == speaker.strip()
                )

            q = q.filter(
                TranscriptSegment.text.ilike(
                    f"%{clean_query}%"
                )
            )

            rows = (
                q.order_by(
                    TranscriptSegment.segment_id
                )
                .limit(limit)
                .all()
            )

            return [
                {
                    "score": 1.0,
                    "score_type": "keyword",
                    "job_id": transcript.job_id,
                    "segment_id": segment.segment_id,
                    "speaker": segment.speaker,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "embedding_source": None,
                    "diarization_source": None,
                    "alignment_source": None,
                    "keyword_score": 1.0,
                    "semantic_score": None
                }
                for transcript, segment in rows
            ]

        finally:
            db.close()

    def get_audio_key_by_job_id(
        self,
        job_id: str
    ) -> str | None:
        db = SessionLocal()

        try:
            clean_job_id = job_id.strip()

            job = (
                db.query(Job)
                .filter(Job.id == clean_job_id)
                .first()
            )

            if job is None:
                return None

            return job.audio_key

        finally:
            db.close()

    def delete_transcript_by_job_id(
        self,
        job_id: str
    ) -> bool:
        db = SessionLocal()

        try:
            clean_job_id = job_id.strip()

            transcript = (
                db.query(Transcript)
                .filter(Transcript.job_id == clean_job_id)
                .first()
            )

            if transcript is None:
                return False

            recording = (
                db.query(Recording)
                .filter(Recording.job_id == clean_job_id)
                .first()
            )

            if recording is not None:
                db.delete(recording)

            db.delete(transcript)

            job = (
                db.query(Job)
                .filter(Job.id == clean_job_id)
                .first()
            )

            if job is not None:
                db.delete(job)

            db.commit()

            return True

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()