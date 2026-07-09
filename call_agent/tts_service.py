"""Silero TTS wrapper with an on-disk WAV cache. Offline."""
from __future__ import annotations

import hashlib
import os
import wave

import numpy as np


def _resample_to_16k(audio: np.ndarray, src_rate: int) -> np.ndarray:
    if src_rate == 16000:
        return audio
    ratio = 16000 / src_rate
    n_out = int(len(audio) * ratio)
    xp = np.linspace(0, 1, num=len(audio), endpoint=False)
    x = np.linspace(0, 1, num=n_out, endpoint=False)
    return np.interp(x, xp, audio).astype(np.float32)


def _write_wav_int16(path: str, audio16k: np.ndarray) -> None:
    clipped = np.clip(audio16k, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())


class TTSService:
    def __init__(self, settings, model=None):
        self._settings = settings
        self._model = model
        os.makedirs(settings.tts_cache_dir, exist_ok=True)

    def _ensure_model(self):
        if self._model is None:
            import torch  # deferred; not needed in tests
            importer = torch.package.PackageImporter(self._settings.silero_model_path)
            self._model = importer.load_pickle("tts_models", "model")
            self._model.to(torch.device("cpu"))
        return self._model

    def _cache_path(self, text: str) -> str:
        key = f"{text}|{self._settings.silero_speaker}|{self._settings.tts_sample_rate}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return os.path.join(self._settings.tts_cache_dir, f"{digest}.wav")

    def synthesize(self, text: str) -> str:
        path = self._cache_path(text)
        if os.path.exists(path):
            return path
        model = self._ensure_model()
        rate = self._settings.tts_sample_rate
        out = model.apply_tts(text=text, speaker=self._settings.silero_speaker, sample_rate=rate)
        audio = np.asarray(out, dtype=np.float32)
        _write_wav_int16(path, _resample_to_16k(audio, rate))
        return path

    def warm_cache(self, phrases: list[str]) -> None:
        for p in phrases:
            self.synthesize(p)
