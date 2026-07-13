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
                 on_event=None, now=time.monotonic, check_submitter=None):
        self.call_id = call_id
        self._asr = asr
        self._detector = detector
        self._dialog = dialog
        self._tts = tts
        self._recorder = recorder
        self._on_event = on_event or (lambda *a, **k: None)
        self._now = now
        self._check_submitter = check_submitter
        self._pending_check = None
        self._semantic_verdict = False
        self._transcript_lines: list[str] = []
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

    def _resolve_pending_check(self) -> list[AgentAction] | None:
        if self._pending_check is None:
            return None
        if not self._pending_check.done():
            return None
        is_scam = bool(self._pending_check.result())
        self._pending_check = None
        if is_scam:
            self._semantic_verdict = True
            self._state = CallState.HANGUP
            self._ended_reason = "detected_scam"
            speak = self._emit_agent(self._dialog.before_hangup_line())
            return [speak, AgentAction(type="hangup", wav_path=None, text="")]
        return None

    def _check_semantically(self) -> list[AgentAction] | None:
        if self._pending_check is not None:
            resolved_actions = self._resolve_pending_check()
            if resolved_actions is not None:
                return resolved_actions
            if self._pending_check is not None:
                return [self._emit_agent(self._dialog.filler())]
            return None

        if self._check_submitter is not None:
            _, score, threshold = self._detector.leading_score()
            if 0 < score < threshold:
                transcript_so_far = "\n".join(self._transcript_lines)
                self._pending_check = self._check_submitter(transcript_so_far)
                return [self._emit_agent(self._dialog.filler())]

        return None

    def on_pcm(self, pcm_bytes: bytes) -> list[AgentAction]:
        self._recorder.write_caller(pcm_bytes)
        res = self._asr.accept(pcm_bytes)
        text = res.get("final")
        if not text:
            return []
        hits = self._detector.feed(text)
        delta = sum(h.weight for h in hits)
        self._on_event(self._elapsed(), "caller", text, delta)
        self._transcript_lines.append(text)
        verdict, scenario, conf = self._detector.verdict()

        if verdict != "scam":
            semantic_actions = self._check_semantically()
            if semantic_actions is not None:
                return semantic_actions

        reply = self._dialog.on_caller_utterance(text, verdict)
        if reply.hang_up:
            self._state = CallState.HANGUP
            self._ended_reason = "detected_scam"
            return [AgentAction(type="hangup", wav_path=None, text="")]
        return [self._emit_agent(reply.text)]

    def tick(self, not_scam_timeout_sec: int) -> list[AgentAction]:
        resolved_actions = self._resolve_pending_check()
        if resolved_actions is not None:
            return resolved_actions

        if self._state == CallState.TALKING and self._elapsed() >= not_scam_timeout_sec:
            self._state = CallState.TAKE_MESSAGE
            self._ended_reason = "took_message"
            return [self._emit_agent(self._dialog.take_message_line())]
        return []

    def result(self) -> CallResult:
        verdict, scenario, conf = self._detector.verdict()
        if self._semantic_verdict:
            leading_key, score, threshold = self._detector.leading_score()
            conf = min(100, round(score / threshold * 100)) if threshold else 100
            return CallResult("scam", leading_key or "ai_semantic_check", conf, self._ended_reason)
        return CallResult(verdict, scenario, conf, self._ended_reason)
