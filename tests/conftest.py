"""
Pytest configuration for CI.

Heavy ML libraries (torch, pyannote, speechbrain, etc.) are not installed
in the CI environment. We mock them via sys.modules BEFORE any app module
is imported, then replace the FastAPI startup handler with a no-op so tests
can run without real services (DB, MinIO, Qdrant).
"""
import sys
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Mock heavy ML dependencies — must happen before any app import
# ---------------------------------------------------------------------------
_HEAVY_MODULES = [
    "torch", "torch.nn", "torch.cuda", "torch.device",
    "torchaudio",
    "speechbrain", "speechbrain.inference", "speechbrain.inference.speaker",
    "pyannote", "pyannote.audio", "pyannote.core",
    "faster_whisper",
    "sentence_transformers",
    "soundfile",
    "scipy", "scipy.io", "scipy.io.wavfile",
    "ctranslate2",
    "onnxruntime",
]
for _mod in _HEAVY_MODULES:
    sys.modules.setdefault(_mod, MagicMock())


# ---------------------------------------------------------------------------
# Replace FastAPI startup with a no-op so tests don't need real services
# ---------------------------------------------------------------------------
import pytest  # noqa: E402  (must come after sys.modules patching)


@pytest.fixture(autouse=True, scope="session")
def disable_startup():
    from api.main import app
    app.router.on_startup.clear()
    app.router.on_startup.append(AsyncMock())
