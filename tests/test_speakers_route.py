import io
import struct
import wave
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from api.auth import verify_api_key


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


def test_create_speaker_without_audio():
    app.dependency_overrides[verify_api_key] = _override_auth
    client = TestClient(app)

    with patch("database.crud.create_speaker", return_value=_make_mock_speaker()):
        response = client.post("/v1/speakers", data={"name": "Alice"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test"
    assert data["kind"] == "registered"


def test_create_speaker_with_valid_audio(tmp_path):
    app.dependency_overrides[verify_api_key] = _override_auth
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
            "/v1/speakers",
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
    app.dependency_overrides[verify_api_key] = _override_auth
    client = TestClient(app)

    wav_bytes = _make_wav_bytes(duration_sec=5.0)
    norm_wav = str(tmp_path / "norm.wav")
    with open(norm_wav, "wb") as f:
        f.write(_make_wav_bytes(duration_sec=5.0))

    with patch("api.routes.speakers.normalize_audio", return_value=norm_wav):
        response = client.post(
            "/v1/speakers",
            data={"name": "Carol"},
            files={"audio": ("short.wav", wav_bytes, "audio/wav")}
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "too short" in response.json()["detail"]


def test_create_speaker_returns_422_when_embedding_fails(tmp_path):
    app.dependency_overrides[verify_api_key] = _override_auth
    client = TestClient(app)

    wav_bytes = _make_wav_bytes(duration_sec=12.0)
    norm_wav = str(tmp_path / "norm.wav")
    with open(norm_wav, "wb") as f:
        f.write(_make_wav_bytes(duration_sec=12.0))

    with patch("api.routes.speakers.normalize_audio", return_value=norm_wav), \
         patch("api.routes.speakers.VoiceEmbeddingService") as mock_svc_cls:
        mock_svc_cls.return_value.extract_embedding.return_value = None

        response = client.post(
            "/v1/speakers",
            data={"name": "Dave"},
            files={"audio": ("bad.wav", wav_bytes, "audio/wav")}
        )

    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "embedding" in response.json()["detail"]


def test_delete_speaker_cleans_qdrant():
    app.dependency_overrides[verify_api_key] = _override_auth
    client = TestClient(app)

    with patch("database.crud.delete_speaker", return_value=True), \
         patch("api.routes.speakers.SpeakerIdentificationService") as mock_id_cls:
        response = client.delete("/v1/speakers/1")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_id_cls.return_value.delete_speaker.assert_called_once_with(1)


def test_merge_speakers_cleans_source_qdrant():
    app.dependency_overrides[verify_api_key] = _override_auth
    client = TestClient(app)

    with patch("database.crud.merge_speakers", return_value="merged"), \
         patch("api.routes.speakers.SpeakerIdentificationService") as mock_id_cls:
        response = client.post("/v1/speakers/1/merge", json={"target_speaker_id": 2})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    mock_id_cls.return_value.delete_speaker.assert_called_once_with(1)
