from math import ceil

from sqlalchemy import func

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

    def save_pipeline_result(self, run_result) -> int | None:
        if run_result.transcript is None:
            return None

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

            full_text = run_result.transcript.full_text or ""
            transcript = Transcript(
                job_id=run_result.job_id,
                status=run_result.status,
                success=run_result.success,
                full_text=full_text,
                full_text_vector=func.to_tsvector("simple", full_text),
                language=run_result.transcript.language,
                duration_sec=run_result.transcript.duration_sec,
            )

            db.add(transcript)
            db.flush()

            for segment in run_result.transcript.segments:
                db_segment = TranscriptSegment(
                    transcript_id=transcript.id,
                    segment_id=segment.id,
                    speaker=segment.speaker,
                    speaker_id=None,
                    start=segment.start,
                    end=segment.end,
                    text=segment.text,
                    overlap=segment.overlap,
                    words=[
                        {
                            "w": word.word,
                            "start": word.start,
                            "end": word.end,
                            "conf": word.confidence,
                        }
                        for word in segment.words
                    ],
                )

                db.add(db_segment)

            db.commit()

            return transcript.id

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

    def get_transcript_id_by_job_id(
        self,
        job_id: str
    ) -> int | None:
        db = SessionLocal()

        try:
            transcript = (
                db.query(Transcript)
                .filter(Transcript.job_id == job_id.strip())
                .first()
            )

            if transcript is None:
                return None

            return transcript.id

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

            from database.models import Occurrence, Speaker

            occurrences = (
                db.query(Occurrence, Speaker)
                .join(Speaker, Occurrence.speaker_id == Speaker.id)
                .filter(Occurrence.transcript_id == transcript.id)
                .order_by(Occurrence.local_label)
                .all()
            )

            speakers = [
                {
                    "local_label": occurrence.local_label,
                    "speaker_id": speaker.id,
                    "display_name": speaker.name if speaker.kind == "registered" else None,
                    "match_score": occurrence.match_score,
                }
                for occurrence, speaker in occurrences
            ]

            return {
                "job_id": transcript.job_id,
                "status": transcript.status,
                "success": transcript.success,
                "language": transcript.language,
                "audio": {
                    "duration_sec": transcript.duration_sec,
                    "sample_rate": 16000,
                    "channels": 1,
                },
                "speakers": speakers,
                "transcript": {
                    "full_text": transcript.full_text,
                    "segments": [
                        {
                            "id": segment.segment_id,
                            "start": segment.start,
                            "end": segment.end,
                            "speaker": segment.speaker,
                            "speaker_id": segment.speaker_id,
                            "text": segment.text,
                            "overlap": segment.overlap,
                            "words": segment.words or [],
                        }
                        for segment in segments
                    ]
                },
                "error": None
            }

        finally:
            db.close()

    def list_transcripts(
        self,
        page: int = 1,
        page_size: int = 20,
        speaker_id: int | None = None,
        status: str | None = None,
    ) -> dict:
        db = SessionLocal()

        try:
            q = db.query(Transcript)

            if status is not None:
                q = q.filter(Transcript.status == status)

            if speaker_id is not None:
                from database.models import Occurrence
                sub = (
                    db.query(Occurrence.transcript_id)
                    .filter(Occurrence.speaker_id == speaker_id)
                    .subquery()
                )
                q = q.filter(Transcript.id.in_(sub))

            total = q.count()
            offset = (page - 1) * page_size
            items = (
                q.order_by(Transcript.created_at.desc())
                .offset(offset)
                .limit(page_size)
                .all()
            )

            return {
                "items": [
                    {
                        "transcript_id": t.id,
                        "job_id": t.job_id,
                        "status": t.status,
                        "language": t.language,
                        "duration_sec": t.duration_sec,
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                    }
                    for t in items
                ],
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": ceil(total / page_size) if total else 0,
            }

        finally:
            db.close()

    def get_segments_by_job_id(
        self,
        job_id: str,
        speaker_id: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        db = SessionLocal()

        try:
            transcript = (
                db.query(Transcript)
                .filter(Transcript.job_id == job_id.strip())
                .first()
            )

            if transcript is None:
                return None

            q = db.query(TranscriptSegment).filter(
                TranscriptSegment.transcript_id == transcript.id
            )

            if speaker_id is not None:
                q = q.filter(TranscriptSegment.speaker_id == speaker_id)

            total = q.count()
            offset = (page - 1) * page_size
            segments = (
                q.order_by(TranscriptSegment.segment_id)
                .offset(offset)
                .limit(page_size)
                .all()
            )

            return {
                "job_id": transcript.job_id,
                "items": [
                    {
                        "id": s.segment_id,
                        "start": s.start,
                        "end": s.end,
                        "speaker": s.speaker,
                        "speaker_id": s.speaker_id,
                        "text": s.text,
                        "overlap": s.overlap,
                        "words": s.words or [],
                    }
                    for s in segments
                ],
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": ceil(total / page_size) if total else 0,
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
                    "speaker_id": segment.speaker_id,
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
            tsquery = func.plainto_tsquery("simple", clean_query)
            seg_vector = func.to_tsvector("simple", TranscriptSegment.text)
            rank = func.ts_rank(seg_vector, tsquery)

            q = (
                db.query(Transcript, TranscriptSegment, rank.label("rank"))
                .join(TranscriptSegment, Transcript.id == TranscriptSegment.transcript_id)
                .filter(seg_vector.op("@@")(tsquery))
            )

            if job_id:
                q = q.filter(Transcript.job_id == job_id.strip())
            if speaker:
                q = q.filter(TranscriptSegment.speaker == speaker.strip())

            rows = q.order_by(rank.desc()).limit(limit).all()

            return [
                {
                    "score": round(float(rank_val), 4),
                    "score_type": "keyword",
                    "job_id": transcript.job_id,
                    "segment_id": segment.segment_id,
                    "speaker": segment.speaker,
                    "speaker_id": segment.speaker_id,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "embedding_source": None,
                    "diarization_source": None,
                    "alignment_source": None,
                    "keyword_score": round(float(rank_val), 4),
                    "semantic_score": None,
                }
                for transcript, segment, rank_val in rows
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