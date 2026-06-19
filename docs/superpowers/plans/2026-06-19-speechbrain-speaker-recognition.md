# SpeechBrain Speaker Recognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace FFT-based voice embeddings with SpeechBrain ECAPA-TDNN (192-dim) and add voice registration to `POST /speakers`.

**Architecture:** `VoiceEmbeddingService` wraps SpeechBrain ECAPA-TDNN loaded once as a class-level singleton on first instantiation. `SpeakerIdentificationService` reads threshold from env and auto-recreates the Qdrant collection when vector size mismatches. `POST /speakers` becomes multipart/form-data with an optional audio file.

**Tech Stack:** speechbrain, torchaudio, torch, qdrant-client, fastapi, sqlalchemy, pytest

## Global Constraints

- Python 3.12+, type hints on all functions
- Model cache path: `/app/models/spkrec-ecapa-voxceleb` (Docker volume `models_cache`)
- `VECTOR_SIZE = 192` (ECAPA-TDNN output dimension)
- `MATCH_THRESHOLD` default `0.80`, configurable via `SPEAKER_MATCH_THRESHOLD` env var
- `kind` column already exists in `database/models.py` and `database/crud.py` — do not re-add
- Do not modify: `pipeline_service.py`, `worker_job_service.py`, `audio_tasks.py`

---

### Task 1: Dependencies + Configuration

**Files:**
- Modify: `requirements.txt`
- Modify: `.env`
- Modify: `docker-compose.yml`

**Interfaces:**
- Produces: `speechbrain` importable in container; `SPEAKER_MATCH_THRESHOLD` env var; volume `models_cache` mounted at `/app/models` for `api` and `worker`

- [ ] **Step 1: Add speechbrain to requirements.txt**

Append to the end of `requirements.txt`:
```
speechbrain
```

- [ ] **Step 2: Add SPEAKER_MATCH_THRESHOLD to .env**

Append to `.env`:
```
SPEAKER_MATCH_THRESHOLD=0.80
```

- [ ] **Step 3: Add models_cache volume to docker-compose.yml**

In the `api` service, update `volumes`:
```yaml
volumes:
  - ./data:/app/data
  - models_cache:/app/models
```

In the `worker` service, update `volumes`:
```yaml
volumes:
  - ./data:/app/data
  - models_cache:/app/models
```

Add `models_cache:` to the top-level `volumes:` section:
```yaml
volumes:
  postgres_data:
  qdrant_data:
  minio_data:
  models_cache:
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt .env docker-compose.yml
git commit -m "feat: add speechbrain dependency and models_cache volume"
```

---

### Task 2: VoiceEmbeddingService — SpeechBrain ECAPA-TDNN

**Files:**
- Modify: `services/voice_embedding_service.py`
- Create: `tests/test_voice_embedding_service.py`

**Interfaces:**
- Produces:
  - `VoiceEmbeddingService.VECTOR_SIZE: int = 192`
  - `VoiceEmbeddingService().is_available() -> bool`
  - `VoiceEmbeddingService().extract_embedding(audio_path: str) -> list[float] | None` — 192-element normalized list or `None` on error

- [ ] **Step 1: Write failing tests**

Create `tests/test_voice_embedding_service.py`:
```python
import io
import struct
import wave
from unittest.mock import MagicMock, patch

import numpy as np
import torch


def _make_mock_model(dim: int = 192):
    mock_model = MagicMock()
    mock_model.encode_batch.return_value = torch.rand(1, 1, dim)
    return mock_model


def _write_wav(path: str, duration_sec: float = 5.0, sample_rate: int = 16000) -> None:
    n = int(sample_rate * duration_sec)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"{n}h", *([1000] * n)))


def test_vector_size_constant():
    from services.voice_embedding_service import VoiceEmbeddingService
    assert VoiceEmbeddingService.VECTOR_SIZE == 192


def test_is_available_returns_true():
    with patch(
        "speechbrain.inference.speaker.EncoderClassifier.from_hparams",
        return_value=_make_mock_model()
    ):
        from services.voice_embedding_service import VoiceEmbeddingService
        VoiceEmbeddingService._model = None
        service = VoiceEmbeddingService()
        assert service.is_available() is True


def test_extract_embedding_returns_192_dim_list(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    _write_wav(wav_path)

    with patch(
        "speechbrain.inference.speaker.EncoderClassifier.from_hparams",
        return_value=_make_mock_model(192)
    ):
        from services.voice_embedding_service import VoiceEmbeddingService
        VoiceEmbeddingService._model = None
        service = VoiceEmbeddingService()
        result = service.extract_embedding(wav_path)

    assert result is not None
    assert len(result) == 192
    assert isinstance(result[0], float)


def test_extract_embedding_returns_normalized_vector(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    _write_wav(wav_path)

    with patch(
        "speechbrain.inference.speaker.EncoderClassifier.from_hparams",
        return_value=_make_mock_model(192)
    ):
        from services.voice_embedding_service import VoiceEmbeddingService
        VoiceEmbeddingService._model = None
        service = VoiceEmbeddingService()
        result = service.extract_embedding(wav_path)

    norm = np.linalg.norm(result)
    assert abs(norm - 1.0) < 1e-5


def test_extract_embedding_returns_none_on_missing_file():
    with patch(
        "speechbrain.inference.speaker.EncoderClassifier.from_hparams",
        return_value=_make_mock_model()
    ):
        from services.voice_embedding_service import VoiceEmbeddingService
        VoiceEmbeddingService._model = None
        service = VoiceEmbeddingService()
        result = service.extract_embedding("/nonexistent/path.wav")

    assert result is None


def test_model_loaded_once_as_singleton(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    _write_wav(wav_path)

    mock_model = _make_mock_model()
    with patch(
        "speechbrain.inference.speaker.EncoderClassifier.from_hparams",
        return_value=mock_model
    ) as mock_loader:
        from services.voice_embedding_service import VoiceEmbeddingService
        VoiceEmbeddingService._model = None
        VoiceEmbeddingService()
        VoiceEmbeddingService()

    mock_loader.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_voice_embedding_service.py -v
```
Expected: FAILED (old FFT implementation doesn't use SpeechBrain)

- [ ] **Step 3: Rewrite services/voice_embedding_service.py**

```python
import logging
import os

import numpy as np
import torch
import torchaudio

logger = logging.getLogger(__name__)

_MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/app/models")


class VoiceEmbeddingService:
    VECTOR_SIZE = 192

    _model = None

    def __init__(self):
        if VoiceEmbeddingService._model is None:
            from speechbrain.inference.speaker import EncoderClassifier
            logger.info("Loading SpeechBrain ECAPA-TDNN model...")
            VoiceEmbeddingService._model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=os.path.join(_MODEL_CACHE_DIR, "spkrec-ecapa-voxceleb"),
                run_opts={"device": "cpu"}
            )
            logger.info("SpeechBrain ECAPA-TDNN model loaded.")

    def is_available(self) -> bool:
        return True

    def extract_embedding(self, audio_path: str) -> list[float] | None:
        try:
            signal, sample_rate = torchaudio.load(audio_path)

            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate,
                    new_freq=16000
                )
                signal = resampler(signal)

            if signal.shape[0] > 1:
                signal = signal.mean(dim=0, keepdim=True)

            with torch.no_grad():
                embeddings = VoiceEmbeddingService._model.encode_batch(signal)

            vector = embeddings.squeeze().cpu().numpy().astype(np.float32)

            norm = float(np.linalg.norm(vector))
            if norm > 0:
                vector = vector / norm

            logger.info("Voice embedding extracted: dim=%s", len(vector))
            return vector.tolist()

        except Exception as error:
            logger.warning("Voice embedding extraction failed: %s", error)
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_voice_embedding_service.py -v
```
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add services/voice_embedding_service.py tests/test_voice_embedding_service.py
git commit -m "feat: replace FFT embeddings with SpeechBrain ECAPA-TDNN"
```

---

### Task 3: SpeakerIdentificationService — VECTOR_SIZE + threshold + collection recreation

**Files:**
- Modify: `services/speaker_identification_service.py`
- Create: `tests/test_speaker_identification_service.py`

**Interfaces:**
- Consumes: `VoiceEmbeddingService.VECTOR_SIZE = 192` (Task 2)
- Produces:
  - `SpeakerIdentificationService.VECTOR_SIZE: int = 192`
  - `SpeakerIdentificationService.MATCH_THRESHOLD: float` — from `SPEAKER_MATCH_THRESHOLD` env (default `0.80`)
  - `SpeakerIdentificationService().find_speaker(embedding: list[float], excluded_speaker_ids: set[int] | None) -> tuple[int | None, float | None]`
  - `SpeakerIdentificationService().save_embedding(speaker_id: int, embedding: list[float]) -> None`
  - `SpeakerIdentificationService().delete_speaker(speaker_id: int) -> None`
  - `_ensure_collection()` drops and recreates collection when existing `vector_size != VECTOR_SIZE`

- [ ] **Step 1: Write failing tests**

Create `tests/test_speaker_identification_service.py`:
```python
import os
from unittest.mock import MagicMock, patch


def _make_mock_client(existing_size: int | None = None):
    client = MagicMock()
    collections = MagicMock()

    if existing_size is None:
        collections.collections = []
    else:
        col = MagicMock()
        col.name = "speaker_voices"
        collections.collections = [col]
        col_info = MagicMock()
        col_info.config.params.vectors.size = existing_size
        client.get_collection.return_value = col_info

    client.get_collections.return_value = collections
    return client


def test_vector_size_is_192():
    from services.speaker_identification_service import SpeakerIdentificationService
    assert SpeakerIdentificationService.VECTOR_SIZE == 192


def test_match_threshold_default_is_0_80(monkeypatch):
    monkeypatch.delenv("SPEAKER_MATCH_THRESHOLD", raising=False)
    import importlib, services.speaker_identification_service as mod
    importlib.reload(mod)
    assert mod.SpeakerIdentificationService.MATCH_THRESHOLD == 0.80


def test_match_threshold_reads_from_env(monkeypatch):
    monkeypatch.setenv("SPEAKER_MATCH_THRESHOLD", "0.75")
    import importlib, services.speaker_identification_service as mod
    importlib.reload(mod)
    assert mod.SpeakerIdentificationService.MATCH_THRESHOLD == 0.75


def test_ensure_collection_creates_when_missing():
    client = _make_mock_client(existing_size=None)
    with patch("qdrant_client.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        SpeakerIdentificationService()
    client.create_collection.assert_called_once()
    client.delete_collection.assert_not_called()


def test_ensure_collection_recreates_on_size_mismatch():
    client = _make_mock_client(existing_size=512)
    with patch("qdrant_client.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        SpeakerIdentificationService()
    client.delete_collection.assert_called_once_with("speaker_voices")
    client.create_collection.assert_called_once()


def test_ensure_collection_skips_when_size_matches():
    client = _make_mock_client(existing_size=192)
    with patch("qdrant_client.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        SpeakerIdentificationService()
    client.delete_collection.assert_not_called()
    client.create_collection.assert_not_called()


def test_find_speaker_returns_none_when_no_points():
    client = _make_mock_client(existing_size=192)
    result = MagicMock()
    result.points = []
    client.query_points.return_value = result
    with patch("qdrant_client.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        service = SpeakerIdentificationService()
        speaker_id, score = service.find_speaker([0.0] * 192)
    assert speaker_id is None
    assert score is None


def test_find_speaker_returns_id_when_score_above_threshold():
    client = _make_mock_client(existing_size=192)
    point = MagicMock()
    point.score = 0.92
    point.payload = {"speaker_id": 42}
    result = MagicMock()
    result.points = [point]
    client.query_points.return_value = result
    with patch("qdrant_client.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        service = SpeakerIdentificationService()
        speaker_id, score = service.find_speaker([0.0] * 192)
    assert speaker_id == 42
    assert score == 0.92


def test_find_speaker_returns_none_when_score_below_threshold():
    client = _make_mock_client(existing_size=192)
    point = MagicMock()
    point.score = 0.65
    point.payload = {"speaker_id": 42}
    result = MagicMock()
    result.points = [point]
    client.query_points.return_value = result
    with patch("qdrant_client.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        service = SpeakerIdentificationService()
        speaker_id, score = service.find_speaker([0.0] * 192)
    assert speaker_id is None
    assert score == 0.65
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_speaker_identification_service.py -v
```
Expected: FAILED on VECTOR_SIZE and MATCH_THRESHOLD assertions

- [ ] **Step 3: Update services/speaker_identification_service.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_speaker_identification_service.py -v
```
Expected: 9 PASSED

- [ ] **Step 5: Commit**

```bash
git add services/speaker_identification_service.py tests/test_speaker_identification_service.py
git commit -m "feat: VECTOR_SIZE=192, configurable threshold, auto-recreate Qdrant collection"
```

---

### Task 4: SpeakerResponse schema + POST /speakers with audio

**Files:**
- Modify: `schemas/api/speaker_schema.py`
- Modify: `api/routes/speakers.py`
- Create: `tests/test_speakers_route.py`

**Interfaces:**
- Consumes:
  - `VoiceEmbeddingService().extract_embedding(audio_path: str) -> list[float] | None` (Task 2)
  - `SpeakerIdentificationService().save_embedding(speaker_id: int, embedding: list[float]) -> None` (Task 3)
  - `normalize_audio(input_path: str, output_path: str) -> str` from `services.audio_service`
  - `crud.create_speaker(db: Session, name: str, phone: str | None) -> Speaker`
- Produces:
  - `SpeakerResponse.kind: str` in all speaker API responses
  - `POST /speakers` accepts `multipart/form-data`: `name` (str, required), `phone` (str, optional), `audio` (UploadFile, optional)
  - 400 if audio duration < 10 seconds
  - 422 if embedding extraction fails

- [ ] **Step 1: Write failing tests**

Create `tests/test_speakers_route.py`:
```python
import io
import struct
import wave
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.auth import require_scope


def _override_auth():
    mock_key = MagicMock()
    mock_key.scopes = "admin"
    return mock_key


def _make_wav_bytes(duration_sec: float, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    n = int(sample_rate * duration_sec)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"{n}h", *([1000] * n)))
    buf.seek(0)
    return buf.read()


def _make_mock_speaker(speaker_id: int = 1, name: str = "Test") -> MagicMock:
    mock = MagicMock()
    mock.id = speaker_id
    mock.name = name
    mock.phone = None
    mock.kind = "registered"
    mock.created_at = datetime.utcnow()
    return mock


def test_speaker_response_has_kind_field():
    from schemas.api.speaker_schema import SpeakerResponse
    assert "kind" in SpeakerResponse.model_fields


def test_create_speaker_without_audio(tmp_path):
    app.dependency_overrides[require_scope("write")] = _override_auth
    client = TestClient(app)

    with patch("database.crud.create_speaker", return_value=_make_mock_speaker()):
        response = client.post("/speakers", data={"name": "Alice"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test"
    assert data["kind"] == "registered"


def test_create_speaker_with_valid_audio(tmp_path):
    app.dependency_overrides[require_scope("write")] = _override_auth
    client = TestClient(app)

    wav_bytes = _make_wav_bytes(duration_sec=12.0)
    norm_wav = str(tmp_path / "norm.wav")
    with open(norm_wav, "wb") as f:
        f.write(_make_wav_bytes(duration_sec=12.0))

    mock_speaker = _make_mock_speaker()

    with patch("database.crud.create_speaker", return_value=mock_speaker), \
         patch("api.routes.speakers.normalize_audio", return_value=norm_wav), \
         patch("api.routes.speakers.VoiceEmbeddingService") as mock_svc_cls, \
         patch("api.routes.speakers.SpeakerIdentificationService") as mock_id_cls:
        mock_svc_cls.return_value.extract_embedding.return_value = [0.1] * 192
        mock_id_cls.return_value.save_embedding.return_value = None

        response = client.post(
            "/speakers",
            data={"name": "Bob"},
            files={"audio": ("sample.wav", wav_bytes, "audio/wav")}
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_id_cls.return_value.save_embedding.assert_called_once_with(
        speaker_id=1,
        embedding=[0.1] * 192
    )


def test_create_speaker_rejects_audio_under_10s(tmp_path):
    app.dependency_overrides[require_scope("write")] = _override_auth
    client = TestClient(app)

    wav_bytes = _make_wav_bytes(duration_sec=5.0)
    norm_wav = str(tmp_path / "norm.wav")
    with open(norm_wav, "wb") as f:
        f.write(_make_wav_bytes(duration_sec=5.0))

    with patch("api.routes.speakers.normalize_audio", return_value=norm_wav):
        response = client.post(
            "/speakers",
            data={"name": "Carol"},
            files={"audio": ("short.wav", wav_bytes, "audio/wav")}
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "too short" in response.json()["detail"]


def test_create_speaker_returns_422_when_embedding_fails(tmp_path):
    app.dependency_overrides[require_scope("write")] = _override_auth
    client = TestClient(app)

    wav_bytes = _make_wav_bytes(duration_sec=12.0)
    norm_wav = str(tmp_path / "norm.wav")
    with open(norm_wav, "wb") as f:
        f.write(_make_wav_bytes(duration_sec=12.0))

    with patch("api.routes.speakers.normalize_audio", return_value=norm_wav), \
         patch("api.routes.speakers.VoiceEmbeddingService") as mock_svc_cls:
        mock_svc_cls.return_value.extract_embedding.return_value = None

        response = client.post(
            "/speakers",
            data={"name": "Dave"},
            files={"audio": ("bad.wav", wav_bytes, "audio/wav")}
        )

    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "embedding" in response.json()["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_speakers_route.py -v
```
Expected: FAILED — `kind` missing from schema, POST endpoint doesn't accept multipart

- [ ] **Step 3: Add kind to SpeakerResponse in schemas/api/speaker_schema.py**

```python
class SpeakerResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    kind: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
```

- [ ] **Step 4: Rewrite api/routes/speakers.py**

```python
import logging
import tempfile
import wave
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from api.auth import require_scope
from database import crud
from database.session import SessionLocal
from schemas.api.speaker_schema import (
    RecordingResponse,
    SpeakerDeleteResponse,
    SpeakerMergeRequest,
    SpeakerMergeResponse,
    SpeakerResponse,
    SpeakersPageResponse,
    SpeakerUpdate,
)
from services.audio_service import normalize_audio
from services.speaker_identification_service import SpeakerIdentificationService
from services.voice_embedding_service import VoiceEmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/speakers", tags=["Speakers"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_voice_embedding(audio: UploadFile) -> list[float]:
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    tmp_raw = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp_raw.close()
    tmp_wav.close()

    try:
        with open(tmp_raw.name, "wb") as f:
            f.write(audio.file.read())

        normalized = normalize_audio(
            input_path=tmp_raw.name,
            output_path=tmp_wav.name
        )

        with wave.open(normalized, "rb") as wf:
            duration = wf.getnframes() / wf.getframerate()

        if duration < 10.0:
            raise HTTPException(
                status_code=400,
                detail="audio too short, minimum 10 seconds"
            )

        embedding = VoiceEmbeddingService().extract_embedding(normalized)

        if embedding is None:
            raise HTTPException(
                status_code=422,
                detail="failed to extract voice embedding"
            )

        return embedding

    finally:
        Path(tmp_raw.name).unlink(missing_ok=True)
        Path(tmp_wav.name).unlink(missing_ok=True)


@router.post(
    "",
    response_model=SpeakerResponse,
    summary="Create speaker",
    description=(
        "Creates a new registered speaker. "
        "Optionally accepts an audio sample (≥ 10 s) to register the speaker's voice "
        "in the vector database for cross-recording identification."
    ),
    dependencies=[Depends(require_scope("write"))]
)
def create_speaker(
    name: str = Form(..., min_length=1, description="Speaker display name"),
    phone: Optional[str] = Form(None, description="Optional phone number"),
    audio: Optional[UploadFile] = File(None, description="Audio sample ≥ 10 s"),
    db: Session = Depends(get_db)
):
    embedding: list[float] | None = None

    if audio is not None:
        embedding = _extract_voice_embedding(audio)

    speaker = crud.create_speaker(db=db, name=name, phone=phone)

    if embedding is not None:
        SpeakerIdentificationService().save_embedding(
            speaker_id=speaker.id,
            embedding=embedding
        )
        logger.info("Registered voice for speaker_id=%s", speaker.id)

    return speaker


@router.get(
    "",
    response_model=SpeakersPageResponse,
    summary="List speakers",
    description="Returns speakers from Postgres with pagination.",
    dependencies=[Depends(require_scope("read"))]
)
def list_speakers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    return crud.get_speakers_paginated(db=db, page=page, page_size=page_size)


@router.patch(
    "/{speaker_id}",
    response_model=SpeakerResponse,
    summary="Update speaker",
    description="Updates speaker name or phone.",
    dependencies=[Depends(require_scope("write"))]
)
def update_speaker(
    speaker_id: int,
    data: SpeakerUpdate,
    db: Session = Depends(get_db)
):
    speaker = crud.update_speaker(
        db=db,
        speaker_id=speaker_id,
        name=data.name,
        phone=data.phone
    )
    if speaker is None:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return speaker


@router.delete(
    "/{speaker_id}",
    response_model=SpeakerDeleteResponse,
    summary="Delete speaker",
    description="Deletes speaker and all linked recordings and occurrences.",
    dependencies=[Depends(require_scope("write"))]
)
def delete_speaker(
    speaker_id: int,
    db: Session = Depends(get_db)
):
    deleted = crud.delete_speaker(db=db, speaker_id=speaker_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return {"message": f"Speaker {speaker_id} deleted"}


@router.post(
    "/{speaker_id}/merge",
    response_model=SpeakerMergeResponse,
    summary="Merge speakers",
    description=(
        "Merges source speaker into target speaker. "
        "All recordings and occurrences are reassigned. "
        "Source speaker is deleted."
    ),
    dependencies=[Depends(require_scope("write"))]
)
def merge_speakers(
    speaker_id: int,
    data: SpeakerMergeRequest,
    db: Session = Depends(get_db)
):
    if speaker_id == data.target_speaker_id:
        raise HTTPException(status_code=400, detail="Cannot merge speaker with itself")

    result = crud.merge_speakers(
        db=db,
        source_speaker_id=speaker_id,
        target_speaker_id=data.target_speaker_id
    )

    if result == "source_not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Source speaker {speaker_id} not found"
        )
    if result == "target_not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Target speaker {data.target_speaker_id} not found"
        )

    return {
        "message": f"Speaker {speaker_id} merged into {data.target_speaker_id}",
        "source_speaker_id": speaker_id,
        "target_speaker_id": data.target_speaker_id
    }


@router.get(
    "/{speaker_id}/recordings",
    response_model=list[RecordingResponse],
    summary="Get speaker recordings",
    description="Returns all audio recordings linked to selected speaker.",
    dependencies=[Depends(require_scope("read"))]
)
def get_speaker_recordings(
    speaker_id: int,
    db: Session = Depends(get_db)
):
    speaker = crud.get_speaker(db=db, speaker_id=speaker_id)
    if speaker is None:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return crud.get_recordings_by_speaker(db=db, speaker_id=speaker_id)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_speakers_route.py -v
```
Expected: 5 PASSED

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all tests PASSED

- [ ] **Step 7: Commit**

```bash
git add schemas/api/speaker_schema.py api/routes/speakers.py tests/test_speakers_route.py
git commit -m "feat: add kind to SpeakerResponse, POST /speakers accepts audio for voice registration"
```
