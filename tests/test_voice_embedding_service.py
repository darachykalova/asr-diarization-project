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
