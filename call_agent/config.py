"""Env-driven settings for the call-agent service."""
from __future__ import annotations

import os

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))


class Settings:
    def __init__(self) -> None:
        self.vosk_model_path = os.getenv(
            "VOSK_MODEL_PATH", "/app/models/vosk/vosk-model-small-ru-0.22")
        self.silero_model_path = os.getenv(
            "SILERO_MODEL_PATH", "/app/models/silero/v4_ru.pt")
        self.silero_speaker = os.getenv("SILERO_SPEAKER", "baya")
        self.tts_sample_rate = int(os.getenv("TTS_SAMPLE_RATE", "48000"))
        self.scenarios_dir = os.path.join(_PKG_DIR, "scenarios")
        self.replies_path = os.path.join(_PKG_DIR, "persona", "replies.yaml")
        self.not_scam_timeout_sec = int(os.getenv("NOT_SCAM_TIMEOUT_SEC", "180"))
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.tts_cache_dir = os.getenv("TTS_CACHE_DIR", "/app/data/tts_cache")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
