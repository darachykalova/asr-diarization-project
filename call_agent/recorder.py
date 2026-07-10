"""Records both sides of a call to a WAV, then ships to MinIO + creates a Job."""
from __future__ import annotations

import os
import wave

from database import crud


class CallRecorder:
    def __init__(self, call_id: str, out_dir: str = "/app/data/calls"):
        self._call_id = call_id
        os.makedirs(out_dir, exist_ok=True)
        self._path = os.path.join(out_dir, f"{call_id}.wav")
        self._wav = wave.open(self._path, "wb")
        self._wav.setnchannels(1)
        self._wav.setsampwidth(2)
        self._wav.setframerate(16000)

    def write_caller(self, pcm_bytes: bytes) -> None:
        self._wav.writeframes(pcm_bytes)

    def write_agent(self, pcm_bytes: bytes) -> None:
        self._wav.writeframes(pcm_bytes)

    def close(self) -> str:
        self._wav.close()
        return self._path

    def publish(self, minio, db, object_key: str | None = None) -> tuple[str, str]:
        object_key = object_key or f"calls/{self._call_id}.wav"
        minio.upload_file(self._path, object_key, content_type="audio/wav")
        crud.create_job(db, job_id=self._call_id, status="queued",
                        audio_key=object_key, params={"source": "call_agent"})
        return object_key, self._call_id
