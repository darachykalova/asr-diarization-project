"""
Downloads all ML models at Docker build time so the container runs offline.

Whisper, SpeechBrain and sentence-transformers are always downloaded.
pyannote/speaker-diarization-3.1 is gated — downloaded only when HF_TOKEN is set.
"""

import logging
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/app/models")
HF_TOKEN = os.getenv("HF_TOKEN", "")


def download_whisper() -> None:
    logger.info("Downloading faster-whisper base model...")
    from faster_whisper import WhisperModel

    WhisperModel(
        "base",
        device="cpu",
        compute_type="int8",
        download_root=os.path.join(MODEL_CACHE_DIR, "whisper"),
    )
    logger.info("faster-whisper base model ready.")


def download_speechbrain() -> None:
    logger.info("Downloading SpeechBrain ECAPA-TDNN...")
    from speechbrain.inference.speaker import EncoderClassifier

    EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=os.path.join(MODEL_CACHE_DIR, "spkrec-ecapa-voxceleb"),
        run_opts={"device": "cpu"},
    )
    logger.info("SpeechBrain ECAPA-TDNN ready.")


def download_sentence_transformers() -> None:
    logger.info("Downloading paraphrase-multilingual-MiniLM-L12-v2...")
    from sentence_transformers import SentenceTransformer

    SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    logger.info("SentenceTransformer ready.")


def download_pyannote() -> None:
    if not HF_TOKEN:
        logger.warning(
            "HF_TOKEN not set — skipping pyannote/speaker-diarization-3.1. "
            "Diarization model will be downloaded on first use (requires internet + accepted licence)."
        )
        return

    logger.info("Downloading pyannote/speaker-diarization-3.1...")
    from pyannote.audio import Pipeline

    Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=HF_TOKEN,
    )
    logger.info("pyannote/speaker-diarization-3.1 ready.")


def main() -> None:
    required = [download_whisper, download_speechbrain, download_sentence_transformers]
    failed = []

    for fn in required:
        try:
            fn()
        except Exception as exc:
            logger.error("%s failed: %s", fn.__name__, exc)
            failed.append(fn.__name__)

    try:
        download_pyannote()
    except Exception as exc:
        logger.warning("pyannote download failed (non-fatal): %s", exc)

    if failed:
        logger.error("Required model downloads failed: %s", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
