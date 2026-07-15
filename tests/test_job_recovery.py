"""Тесты самолечения зависших pipeline-задач (нужен запущенный postgres).

Сценарий бага: worker/Redis умирают посреди обработки — строка в jobs
остаётся в processing навсегда. requeue_stuck_jobs находит такие строки
и ставит конвейер заново.
"""
import uuid
from datetime import datetime, timedelta

import pytest

from database.models import Job
from database.session import SessionLocal
from tasks.recovery import requeue_stuck_jobs

pytestmark = pytest.mark.requires_db


def _mk_job(db, status, *, hours_ago, audio_key="calls/test.wav", progress=50):
    jid = f"test-recov-{uuid.uuid4().hex[:8]}"
    ts = datetime.utcnow() - timedelta(hours=hours_ago)
    job = Job(
        id=jid, status=status, audio_key=audio_key, progress=progress,
        created_at=ts,
        started_at=ts if status == "processing" else None,
        finished_at=ts if status in ("done", "failed") else None,
    )
    db.add(job)
    db.commit()
    return jid


def _cleanup(db, ids):
    db.query(Job).filter(Job.id.in_(ids)).delete(synchronize_session=False)
    db.commit()


def test_requeues_old_processing_job():
    db = SessionLocal()
    enqueued = []
    jid = _mk_job(db, "processing", hours_ago=3)
    try:
        requeued = requeue_stuck_jobs(db, enqueue=lambda job: enqueued.append(job.id))
        assert jid in requeued
        assert jid in enqueued
        job = db.query(Job).filter(Job.id == jid).first()
        db.refresh(job)
        assert job.status == "queued"
        assert job.progress == 0
        assert job.started_at is None
    finally:
        _cleanup(db, [jid])
        db.close()


def test_leaves_fresh_processing_job_alone():
    db = SessionLocal()
    enqueued = []
    jid = _mk_job(db, "processing", hours_ago=0.1)
    try:
        requeued = requeue_stuck_jobs(db, enqueue=lambda job: enqueued.append(job.id))
        assert jid not in requeued
        assert jid not in enqueued
        job = db.query(Job).filter(Job.id == jid).first()
        db.refresh(job)
        assert job.status == "processing"
    finally:
        _cleanup(db, [jid])
        db.close()


def test_leaves_finished_jobs_alone():
    db = SessionLocal()
    enqueued = []
    done_id = _mk_job(db, "done", hours_ago=5, progress=100)
    failed_id = _mk_job(db, "failed", hours_ago=5)
    try:
        requeued = requeue_stuck_jobs(db, enqueue=lambda job: enqueued.append(job.id))
        assert done_id not in requeued
        assert failed_id not in requeued
        assert enqueued == [] or all(i not in (done_id, failed_id) for i in enqueued)
    finally:
        _cleanup(db, [done_id, failed_id])
        db.close()


def test_requeues_old_queued_job():
    """queued-задание тоже могло испариться вместе с очередью."""
    db = SessionLocal()
    enqueued = []
    jid = _mk_job(db, "queued", hours_ago=3)
    try:
        requeued = requeue_stuck_jobs(db, enqueue=lambda job: enqueued.append(job.id))
        assert jid in requeued
        assert jid in enqueued
    finally:
        _cleanup(db, [jid])
        db.close()


def test_no_audio_key_marked_failed_not_requeued():
    db = SessionLocal()
    enqueued = []
    jid = _mk_job(db, "processing", hours_ago=3, audio_key=None)
    try:
        requeued = requeue_stuck_jobs(db, enqueue=lambda job: enqueued.append(job.id))
        assert jid not in requeued
        assert jid not in enqueued
        job = db.query(Job).filter(Job.id == jid).first()
        db.refresh(job)
        assert job.status == "failed"
        assert job.error_code == "STUCK_NO_AUDIO"
    finally:
        _cleanup(db, [jid])
        db.close()
