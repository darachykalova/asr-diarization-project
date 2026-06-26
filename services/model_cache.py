import logging
import os
from pathlib import Path

import torch

logger = logging.getLogger(__name__)

_whisper_models: dict = {}
_pyannote_pipeline = None

# faster-whisper stores each model under this cache-dir name. Used to verify a
# model is present locally before loading (offline mode — HF is never called).
WHISPER_CACHE_NAMES = {
    "tiny": "models--Systran--faster-whisper-tiny",
    "base": "models--Systran--faster-whisper-base",
    "large-v2": "models--Systran--faster-whisper-large-v2",
}


def is_whisper_available(model_size: str) -> bool:
    """True if the model's files are present on the local cache volume."""
    name = WHISPER_CACHE_NAMES.get(model_size)
    if name is None:
        return False
    cache_dir = os.getenv("MODEL_CACHE_DIR", "/app/models")
    path = Path(cache_dir) / "whisper" / name
    if not path.exists():
        return False
    return any(f.is_file() and f.stat().st_size > 0 for f in path.rglob("*"))


def get_whisper_model(model_size: str = "base"):
    """Return a cached WhisperModel for this worker process, loading on first call."""
    global _whisper_models
    if model_size not in _whisper_models:
        # Fail fast with a clear message if the model is not present locally
        # (offline mode — Hugging Face is never contacted at runtime).
        if not is_whisper_available(model_size):
            from services.model_registry import ModelNotAvailableError
            raise ModelNotAvailableError(
                f"Whisper model '{model_size}' is not present locally "
                f"(offline mode). Download it into the models cache first."
            )
        from faster_whisper import WhisperModel
        cache_dir = os.getenv("MODEL_CACHE_DIR", "/app/models")
        logger.info("Worker process: loading Whisper model '%s' into cache", model_size)
        _whisper_models[model_size] = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=os.path.join(cache_dir, "whisper"),
        )
        logger.info("Worker process: Whisper model '%s' cached", model_size)
    return _whisper_models[model_size]


def get_pyannote_pipeline():
    """Return a cached pyannote Pipeline for this worker process, loading on first call."""
    global _pyannote_pipeline
    if _pyannote_pipeline is None:
        from services.model_registry import ensure_model
        # Fail fast if the diarization models are not present locally (offline mode).
        ensure_model("pyannote-diarization")
        ensure_model("pyannote-segmentation")
        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            raise RuntimeError(
                "HF_TOKEN is not set. Set Hugging Face token before running diarization."
            )
        from pyannote.audio import Pipeline
        logger.info("Worker process: loading pyannote pipeline into cache")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token,
        )
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _pyannote_pipeline = pipeline.to(device)
        logger.info("Worker process: pyannote pipeline cached (device=%s)", device)
    return _pyannote_pipeline
