"""
Single source of truth for the ML models the application depends on.

Used both as a pre-flight check (scripts/verify_models.py, worker/API startup)
and at the point of use (model loaders) so that — if a model is missing locally
and Hugging Face is unreachable (HF_HUB_OFFLINE=1) — the program fails fast with a
clear, actionable message instead of a cryptic network/cache error.

Resilience guarantee: every model is downloaded once (at Docker build time via
scripts/download_models.py, or restored from MinIO via scripts/sync_models_from_minio.py)
and kept on the local `models_cache` volume. At runtime the app never calls
huggingface.co — it only reads these local paths.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_CACHE_DIR = Path(os.getenv("MODEL_CACHE_DIR", "/app/models"))
HF_HOME = Path(os.getenv("HF_HOME", str(MODEL_CACHE_DIR / "hf")))
HF_HUB = HF_HOME / "hub"


class ModelNotAvailableError(RuntimeError):
    """Raised when a required model is not present locally and cannot be loaded."""


@dataclass(frozen=True)
class ModelSpec:
    key: str           # short id, e.g. "whisper"
    name: str          # human / hub name
    local_path: Path   # sentinel path that must exist and be non-empty
    used_for: str      # which feature needs it
    how_to_get: str    # remediation hint


REQUIRED_MODELS: list[ModelSpec] = [
    ModelSpec(
        key="whisper",
        name="faster-whisper base",
        local_path=MODEL_CACHE_DIR / "whisper" / "models--Systran--faster-whisper-base",
        used_for="speech recognition (ASR)",
        how_to_get="docker build (HF online) or scripts/sync_models_from_minio.py",
    ),
    ModelSpec(
        key="pyannote-diarization",
        name="pyannote/speaker-diarization-3.1",
        local_path=HF_HUB / "models--pyannote--speaker-diarization-3.1",
        used_for="speaker diarization",
        how_to_get="docker build with HF_TOKEN (gated model) or scripts/sync_models_from_minio.py",
    ),
    ModelSpec(
        key="pyannote-segmentation",
        name="pyannote/segmentation-3.0",
        local_path=HF_HUB / "models--pyannote--segmentation-3.0",
        used_for="speaker diarization (segmentation dependency)",
        how_to_get="docker build with HF_TOKEN (gated model) or scripts/sync_models_from_minio.py",
    ),
    ModelSpec(
        key="speechbrain-ecapa",
        name="speechbrain/spkrec-ecapa-voxceleb",
        local_path=MODEL_CACHE_DIR / "spkrec-ecapa-voxceleb" / "embedding_model.ckpt",
        used_for="voice embeddings / speaker identification",
        how_to_get="docker build (HF online) or scripts/sync_models_from_minio.py",
    ),
    ModelSpec(
        key="sentence-transformers",
        name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        local_path=HF_HUB / "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2",
        used_for="semantic search (text embeddings)",
        how_to_get="docker build (HF online) or scripts/sync_models_from_minio.py",
    ),
]

_BY_KEY = {spec.key: spec for spec in REQUIRED_MODELS}


def _is_present(path: Path) -> bool:
    """A model is present if the sentinel exists and holds at least one non-empty file."""
    if not path.exists():
        return False
    if path.is_file():
        return path.stat().st_size > 0
    return any(f.is_file() and f.stat().st_size > 0 for f in path.rglob("*"))


def check(spec: ModelSpec) -> bool:
    return _is_present(spec.local_path)


def missing_models() -> list[ModelSpec]:
    return [spec for spec in REQUIRED_MODELS if not check(spec)]


def ensure_model(key: str) -> None:
    """
    Guard called by a model loader right before loading.

    Raises ModelNotAvailableError with a clear message if the model is not on disk,
    so the program stops instead of silently trying to reach Hugging Face.
    """
    spec = _BY_KEY.get(key)
    if spec is None:
        return  # unknown key — don't block
    if check(spec):
        return
    raise ModelNotAvailableError(
        f"Model '{spec.name}' is required for {spec.used_for} but was not found locally at:\n"
        f"    {spec.local_path}\n"
        f"Hugging Face is not contacted at runtime (offline mode). To fix:\n"
        f"    {spec.how_to_get}"
    )


def ensure_available() -> None:
    """
    Pre-flight gate: raise if ANY required model is missing.
    Call at worker / API startup so the service refuses to start in a broken state.
    """
    missing = missing_models()
    if not missing:
        logger.info("All %d required models present locally.", len(REQUIRED_MODELS))
        return
    lines = [
        f"  - {m.name}  ->  MISSING at {m.local_path}\n      ({m.how_to_get})"
        for m in missing
    ]
    raise ModelNotAvailableError(
        "Cannot start: required ML models are missing locally and Hugging Face "
        "is not used at runtime (offline mode).\n" + "\n".join(lines)
    )
