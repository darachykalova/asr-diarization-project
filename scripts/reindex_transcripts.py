"""
Re-index all transcript segments into Qdrant.

Use after switching the text-embedding model (vector size changes) or to repair
jobs whose Qdrant indexing failed at processing time. Reads segments from
PostgreSQL and re-embeds + upserts them via QdrantService.

    docker compose exec api python scripts/reindex_transcripts.py
"""
import logging
from types import SimpleNamespace

from sqlalchemy import text as sqltext

from database.session import SessionLocal
from services.qdrant_service import QdrantService

logging.basicConfig(level=logging.WARNING)


def main() -> None:
    db = SessionLocal()
    try:
        jobs = db.execute(sqltext("SELECT id, job_id FROM transcripts ORDER BY id")).fetchall()
        print(f"transcripts to reindex: {len(jobs)}")

        qdrant = QdrantService()
        total_segments = 0
        ok_jobs = 0

        for transcript_id, job_id in jobs:
            rows = db.execute(
                sqltext(
                    'SELECT segment_id, text, speaker, start, "end", overlap '
                    "FROM segments WHERE transcript_id = :tid ORDER BY segment_id"
                ),
                {"tid": transcript_id},
            ).fetchall()

            if not rows:
                continue

            segs = [
                SimpleNamespace(
                    id=r[0], text=r[1], speaker=r[2], start=r[3], end=r[4],
                    overlap=r[5], alignment_source="placeholder",
                    diarization_source="pyannote",
                )
                for r in rows
            ]

            if qdrant.save_segments(job_id=job_id, segments=segs):
                ok_jobs += 1
                total_segments += len(segs)
                print(f"  {job_id}: {len(segs)} segments")
            else:
                print(f"  {job_id}: FAILED")

        print(f"\nDONE: {ok_jobs}/{len(jobs)} jobs, {total_segments} segments indexed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
