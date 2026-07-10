"""Orchestrates one call: ASR -> detect -> dialog -> TTS action, with recording."""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum


class CallState(str, Enum):
    GREETING = "greeting"
    TALKING = "talking"
    HANGUP = "hangup"
    TAKE_MESSAGE = "take_message"
    ENDED = "ended"


@dataclass
class AgentAction:
    type: str            # "speak" | "hangup"
    wav_path: str | None
    text: str


@dataclass
class CallResult:
    verdict: str
    scenario: str | None
    confidence: int
    ended_reason: str | None


class CallSession:
    def __init__(self, call_id, asr, detector, dialog, tts, recorder,
                 on_event=None, now=time.monotonic):
        self.call_id = call_id
        self._asr = asr
        self._detector = detector
        self._dialog = dialog
        self._tts = tts
        self._recorder = recorder
        self._on_event = on_event or (lambda *a, **k: None)
        self._now = now
        self._state = CallState.GREETING
        self._t0 = None
        self._ended_reason = None

    def _elapsed(self) -> float:
        return 0.0 if self._t0 is None else self._now() - self._t0

    def _emit_agent(self, text: str) -> AgentAction:
        wav = self._tts.synthesize(text)
        self._on_event(self._elapsed(), "agent", text, 0)
        return AgentAction(type="speak", wav_path=wav, text=text)

    def start(self) -> AgentAction:
        self._t0 = self._now()
        self._state = CallState.TALKING
        return self._emit_agent(self._dialog.greeting())

    def on_pcm(self, pcm_bytes: bytes) -> list[AgentAction]:
        self._recorder.write_caller(pcm_bytes)
        res = self._asr.accept(pcm_bytes)
        text = res.get("final")
        if not text:
            return []
        hits = self._detector.feed(text)
        delta = sum(h.weight for h in hits)
        self._on_event(self._elapsed(), "caller", text, delta)
        verdict, scenario, conf = self._detector.verdict()
        reply = self._dialog.on_caller_utterance(text, verdict)
        if reply.hang_up:
            self._state = CallState.HANGUP
            self._ended_reason = "detected_scam"
            return [AgentAction(type="hangup", wav_path=None, text="")]
        return [self._emit_agent(reply.text)]

    def tick(self, not_scam_timeout_sec: int) -> AgentAction | None:
        if self._state == CallState.TALKING and self._elapsed() >= not_scam_timeout_sec:
            self._state = CallState.TAKE_MESSAGE
            self._ended_reason = "took_message"
            return self._emit_agent(self._dialog.take_message_line())
        return None

    def result(self) -> CallResult:
        verdict, scenario, conf = self._detector.verdict()
        return CallResult(verdict, scenario, conf, self._ended_reason)
