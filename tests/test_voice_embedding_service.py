import struct
import wave
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


pytestmark = pytest.mark.requires_torch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_vector(dim: int = 192) -> np.ndarray:
    """A unit-length numpy vector of length *dim*."""
    v = np.random.rand(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def _make_mock_model(dim: int = 192):
    """Return a mock SpeechBrain model.

    encode_batch() returns a mock whose squeeze().cpu().numpy().astype()
    chain yields a real numpy vector so the normalisation code can run.
    """
    fake_vector = _make_fake_vector(dim)

    mock_emb = MagicMock()
    mock_emb.squeeze.return_value.cpu.return_value.numpy.return_value.astype.return_value = fake_vector

    mock_model = MagicMock()
    mock_model.encode_batch.return_value = mock_emb
    return mock_model


def _fake_sf_read(path: str, **kwargs):
    """Mimic soundfile.read: return (samples×1 float32 array, 16000)."""
    data = np.ones((16000 * 5, 1), dtype=np.float32) * 0.1
    return data, 16000


def _make_torch_mock():
    """Build a minimal torch mock that satisfies extract_embedding's usage.

    Specifically:
    - torch.from_numpy(x) returns a signal mock with .shape[0] == 1
    - torch.no_grad() works as a context manager
    """
    signal_mock = MagicMock()
    # shape[0] must be <= 1 so the "mix down to mono" branch is NOT taken
    signal_mock.shape = (1, 80000)

    torch_mock = MagicMock()
    torch_mock.from_numpy.return_value = signal_mock
    # no_grad() must work as a context manager
    torch_mock.no_grad.return_value.__enter__ = MagicMock(return_value=None)
    torch_mock.no_grad.return_value.__exit__ = MagicMock(return_value=False)
    return torch_mock


@contextmanager
def _embedding_patches(dim: int = 192):
    """Context manager that stacks all patches needed for VoiceEmbeddingService tests."""
    torch_mock = _make_torch_mock()
    mock_model = _make_mock_model(dim)
    with patch("services.model_registry.ensure_model"), \
         patch("speechbrain.inference.speaker.EncoderClassifier.from_hparams",
               return_value=mock_model), \
         patch("services.voice_embedding_service.torch", torch_mock), \
         patch("services.voice_embedding_service.sf.read", side_effect=_fake_sf_read):
        from services.voice_embedding_service import VoiceEmbeddingService
        VoiceEmbeddingService._model = None
        yield VoiceEmbeddingService


def _write_wav(path: str, duration_sec: float = 5.0, sample_rate: int = 16000) -> None:
    n = int(sample_rate * duration_sec)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"{n}h", *([1000] * n)))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_vector_size_constant():
    from services.voice_embedding_service import VoiceEmbeddingService
    assert VoiceEmbeddingService.VECTOR_SIZE == 192


def test_is_available_returns_true():
    with patch("services.model_registry.ensure_model"), \
         patch("speechbrain.inference.speaker.EncoderClassifier.from_hparams",
               return_value=_make_mock_model()):
        from services.voice_embedding_service import VoiceEmbeddingService
        VoiceEmbeddingService._model = None
        service = VoiceEmbeddingService()
        assert service.is_available() is True


def test_extract_embedding_returns_192_dim_list(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    _write_wav(wav_path)

    with _embedding_patches(192) as VoiceEmbeddingService:
        service = VoiceEmbeddingService()
        result = service.extract_embedding(wav_path)

    assert result is not None
    assert len(result) == 192
    assert isinstance(result[0], float)


def test_extract_embedding_returns_normalized_vector(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    _write_wav(wav_path)

    with _embedding_patches(192) as VoiceEmbeddingService:
        service = VoiceEmbeddingService()
        result = service.extract_embedding(wav_path)

    norm = np.linalg.norm(result)
    assert abs(norm - 1.0) < 1e-5


def test_extract_embedding_returns_none_on_missing_file():
    # sf.read is NOT patched here — the MagicMock from conftest will raise when
    # we try to unpack its return value, which extract_embedding catches → None.
    with patch("services.model_registry.ensure_model"), \
         patch("speechbrain.inference.speaker.EncoderClassifier.from_hparams",
               return_value=_make_mock_model()):
        from services.voice_embedding_service import VoiceEmbeddingService
        VoiceEmbeddingService._model = None
        service = VoiceEmbeddingService()
        result = service.extract_embedding("/nonexistent/path.wav")

    assert result is None


def test_model_loaded_once_as_singleton(tmp_path):
    wav_path = str(tmp_path / "test.wav")
    _write_wav(wav_path)

    mock_model = _make_mock_model()
    with patch("services.model_registry.ensure_model"), \
         patch("speechbrain.inference.speaker.EncoderClassifier.from_hparams",
               return_value=mock_model) as mock_loader:
        from services.voice_embedding_service import VoiceEmbeddingService
        VoiceEmbeddingService._model = None
        VoiceEmbeddingService()
        VoiceEmbeddingService()

    mock_loader.assert_called_once()
