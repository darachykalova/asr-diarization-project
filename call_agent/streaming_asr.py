"""Vosk streaming ASR wrapper. Consumes 16 kHz mono Int16LE PCM."""
from __future__ import annotations

import json


class StreamingASR:
    def __init__(self, settings, recognizer=None):
        self._settings = settings
        self._rec = recognizer

    def _ensure_rec(self):
        if self._rec is None:
            from vosk import Model, KaldiRecognizer  # deferred; not needed in tests
            model = Model(self._settings.vosk_model_path)
            self._rec = KaldiRecognizer(model, 16000)
            self._rec.SetWords(True)
        return self._rec

    def accept(self, pcm_bytes: bytes) -> dict:
        rec = self._ensure_rec()
        if rec.AcceptWaveform(pcm_bytes):
            return {"final": json.loads(rec.Result()).get("text", "")}
        return {"partial": json.loads(rec.PartialResult()).get("partial", "")}

    def flush(self) -> str:
        rec = self._ensure_rec()
        return json.loads(rec.FinalResult()).get("text", "")
