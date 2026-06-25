"""Dispatch a chain-mode test job and poll until done."""
import sys
import time
from uuid import uuid4

sys.path.insert(0, "/app")

from database.session import SessionLocal
from database import crud
from tasks.audio_tasks import build_pipeline_chain

JOB_ID = str(uuid4())
INPUT_KEY = "test/audio_short_15s.mp3"

print(f"Dispatching chain job {JOB_ID} ...")

db = SessionLocal()
try:
    crud.create_job(db=db, job_id=JOB_ID, status="queued",
                    audio_key=INPUT_KEY, params={"max_speakers": 1}, idempotency_key=None)
    crud.create_recording(db=db, job_id=JOB_ID, filename="test_chain_3min.mp3", speaker_id=None)
finally:
    db.close()

build_pipeline_chain(
    job_id=JOB_ID,
    input_key=INPUT_KEY,
    max_speakers=1,
).apply_async()

print(f"Chain dispatched. Polling status...")
t0 = time.time()
for _ in range(120):
    time.sleep(10)
    db = SessionLocal()
    try:
        job = crud.get_job_by_id(db=db, job_id=JOB_ID)
        elapsed = int(time.time() - t0)
        print(f"  [{elapsed}s] {job.status} progress={job.progress}")
        if job.status in ("done", "failed", "partial"):
            print(f"\nFinal: {job.status} in {elapsed}s")
            if job.error_message:
                print(f"Error: {job.error_message}")
            break
    finally:
        db.close()
