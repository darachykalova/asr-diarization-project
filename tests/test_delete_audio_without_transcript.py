"""
Удаление аудиозаписи без готовой транскрипции (нужен запущенный postgres/minio/qdrant).

Баг: пользователь не мог удалить запись через фронтенд, пока она обрабатывалась —
сервер отвечал 404 "Запись не найдена", хотя задача (Job) существовала и была
видна в списке. Причина: удаление проверяло наличие Transcript, а не Job.
"""
import uuid
from datetime import datetime

from sqlalchemy import text

from api.routes.transcripts import _delete_transcript_everywhere
from database import crud
from database.session import SessionLocal


def _insert_job_without_transcript(db, job_id: str, status: str = "processing") -> None:
    db.execute(text(
        "INSERT INTO jobs (id, status, progress, created_at) VALUES (:jid, :status, 0, :now)"
    ), {"jid": job_id, "status": status, "now": datetime.utcnow()})
    db.commit()


def _insert_call_for_job(db, call_id: str, job_id: str) -> None:
    db.execute(text(
        "INSERT INTO calls (id, source, started_at, verdict, confidence, job_id) "
        "VALUES (:cid, 'browser', :now, 'undetermined', 0, :jid)"
    ), {"cid": call_id, "jid": job_id, "now": datetime.utcnow()})
    db.commit()


def _cleanup(db, job_id: str, call_id: str | None = None) -> None:
    try:
        if call_id:
            db.execute(text("DELETE FROM calls WHERE id = :cid"), {"cid": call_id})
        db.execute(text("DELETE FROM transcripts WHERE job_id = :jid"), {"jid": job_id})
        db.execute(text("DELETE FROM jobs WHERE id = :jid"), {"jid": job_id})
        db.commit()
    except Exception:
        db.rollback()


def test_delete_transcript_by_job_id_deletes_job_without_transcript():
    db = SessionLocal()
    jid = f"test-del-{uuid.uuid4().hex[:8]}"
    try:
        _insert_job_without_transcript(db, jid)

        deleted = crud.delete_transcript_by_job_id(job_id=jid)

        assert deleted is True
        remaining = db.execute(
            text("SELECT 1 FROM jobs WHERE id = :jid"), {"jid": jid}
        ).first()
        assert remaining is None
    finally:
        _cleanup(db, jid)
        db.close()


def test_delete_everywhere_succeeds_for_job_without_transcript():
    db = SessionLocal()
    jid = f"test-del-{uuid.uuid4().hex[:8]}"
    try:
        _insert_job_without_transcript(db, jid)

        result = _delete_transcript_everywhere(jid)

        assert result["deleted"] is True
        assert result["postgres_deleted"] is True
    finally:
        _cleanup(db, jid)
        db.close()


def test_delete_everywhere_still_404_for_truly_missing_job():
    result = _delete_transcript_everywhere(f"no-such-job-{uuid.uuid4().hex[:8]}")
    assert result["deleted"] is False
    assert result["reason"] == "not_found"


def test_delete_everywhere_succeeds_for_job_linked_to_call():
    """Звонки анти-скам агента пишут job_id в calls.job_id (FK на jobs.id).
    Удаление аудио не должно падать с ForeignKeyViolation — звонок должен
    остаться в истории (для call_stats/MCP), просто без ссылки на job."""
    db = SessionLocal()
    jid = f"test-del-{uuid.uuid4().hex[:8]}"
    cid = f"test-call-{uuid.uuid4().hex[:8]}"
    try:
        _insert_job_without_transcript(db, jid, status="done")
        _insert_call_for_job(db, cid, jid)

        result = _delete_transcript_everywhere(jid)

        assert result["deleted"] is True

        call_row = db.execute(
            text("SELECT job_id FROM calls WHERE id = :cid"), {"cid": cid}
        ).first()
        assert call_row is not None, "call row must survive audio deletion"
        assert call_row[0] is None
    finally:
        _cleanup(db, jid, cid)
        db.close()
