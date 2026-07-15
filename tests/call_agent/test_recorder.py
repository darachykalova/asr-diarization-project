import os
import wave

from call_agent.recorder import CallRecorder


def test_records_and_closes_wav(tmp_path):
    rec = CallRecorder("call-rec-1", out_dir=str(tmp_path))
    rec.write_caller(b"\x01\x00" * 1600)   # 0.1s
    rec.write_agent(b"\x02\x00" * 1600)
    path = rec.close()
    assert os.path.exists(path)
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnframes() == 3200


def test_publish_uploads_and_creates_job(tmp_path):
    rec = CallRecorder("call-rec-2", out_dir=str(tmp_path))
    rec.write_caller(b"\x00\x00" * 100)
    rec.close()

    uploaded = {}

    class FakeMinio:
        def upload_file(self, local_path, object_key, content_type=None):
            uploaded["key"] = object_key
            return object_key
    created = {}

    class FakeDB: ...

    def fake_create_job(db, job_id, status, audio_key, params):
        created.update(job_id=job_id, audio_key=audio_key)
        return None

    import call_agent.recorder as rmod
    orig = rmod.crud.create_job
    rmod.crud.create_job = fake_create_job
    try:
        key, job_id = rec.publish(FakeMinio(), FakeDB())
    finally:
        rmod.crud.create_job = orig
    assert key == "calls/call-rec-2.wav"
    assert job_id == "call-rec-2"
    assert created["audio_key"] == "calls/call-rec-2.wav"
