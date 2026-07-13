# LLM-Backed Scam Verification With Stall Phrases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the rule-based phrase detector scores a caller utterance above zero but below its scenario's threshold, ask the local Ollama model in the background whether the call is a scam, while the agent stalls with filler phrases — and confirmed AI verdicts get a real goodbye line before hangup instead of the current silent hangup.

**Architecture:** `CallSession` (`call_agent/session.py`) gains an injected `check_submitter` callable that submits a background check and returns a `concurrent.futures.Future[bool]`. Each `on_pcm()` turn polls that future instead of blocking: not-yet-done means another filler; done-and-true means a farewell line plus hangup; done-and-false means the conversation resumes normally. `call_agent/main.py` wires the real submitter to a small `ThreadPoolExecutor` calling the new `call_agent/semantic_check.py` module (an Ollama call mirroring the existing `call_agent/summary.py` pattern).

**Tech Stack:** Python (`call_agent` FastAPI service), stdlib `concurrent.futures` for the background check, existing local Ollama (`settings.ollama_url` / `settings.ollama_model`, already used by `call_agent/summary.py`).

## Global Constraints

- The neural-net check is triggered only when the rule-based leading score is strictly between 0 and its scenario's threshold (`0 < score < threshold`) — never on a zero score, never after the rule-based detector has already crossed the threshold on its own.
- At most one background check runs per call at a time — a new ambiguous signal while a check is pending never starts a second one; it just returns another filler.
- While a check is pending (started but not yet resolved), every subsequent caller utterance gets a filler reply, never the normal `keep_talking` reply.
- If the check resolves `True` (scam), the agent speaks one `before_hangup` line and hangs up in the same turn, automatically — it never waits for a further caller reply.
- If the check resolves `False`, the call resumes the normal conversation flow for the current utterance, as if nothing happened.
- A failed or timed-out Ollama call (~15s budget) must resolve to `False` ("not scam") — it must never raise, and must never block the call indefinitely.
- `CallSession` must stay synchronous and unit-testable without real threads or a real Ollama — the background-check dependency is injected, exactly like the existing `now=time.monotonic` and `recognizer` injection points.
- Reuses `settings.ollama_url` / `settings.ollama_model` from `call_agent/config.py` — no new config/env vars.

---

### Task 1: New reply phrases — fillers and pre-hangup line

**Files:**
- Modify: `call_agent/persona/replies.yaml`
- Modify: `call_agent/dialog_engine.py`
- Test: `tests/call_agent/test_dialog_engine.py`

**Interfaces:**
- Produces: `DialogEngine.before_hangup_line() -> str`, used by Task 4's `CallSession._check_semantically()`.

- [ ] **Step 1: Write the failing test**

In `tests/call_agent/test_dialog_engine.py`, update `test_filler_from_pool` to include the two new fillers, and add a new test for the pre-hangup line:

```python
def test_filler_from_pool():
    e = _engine()
    assert e.filler() in ["Сейчас-сейчас, минуточку…", "А? Повторите, пожалуйста.",
                          "Ой, подождите, очки найду.", "Кхм… кхм…",
                          "Ой, погодите, ручку возьму, чтобы записать.",
                          "Так, так… минуточку, соображу."]


def test_before_hangup_line():
    e = _engine()
    assert e.before_hangup_line() in ["Ой, у меня чайник закипел, я перезвоню.",
                                      "Кажется, в дверь звонят, извините, мне пора.",
                                      "Ой, второй телефон звонит, мне надо ответить."]
```

- [ ] **Step 2: Run tests to verify the new one fails**

Run: `python -m pytest tests/call_agent/test_dialog_engine.py -v`
Expected: `test_before_hangup_line` FAILS with `AttributeError: 'DialogEngine' object has no attribute 'before_hangup_line'`. `test_filler_from_pool` also fails at this point (yaml doesn't have the two new fillers yet).

- [ ] **Step 3: Add the new phrases to replies.yaml**

Replace the contents of `call_agent/persona/replies.yaml` with:

```yaml
greeting:
  - "Алло?"
  - "Да, слушаю вас."
fillers:
  - "Сейчас-сейчас, минуточку…"
  - "А? Повторите, пожалуйста."
  - "Ой, подождите, очки найду."
  - "Кхм… кхм…"
  - "Ой, погодите, ручку возьму, чтобы записать."
  - "Так, так… минуточку, соображу."
keep_talking:
  - "Ага… и что?"
  - "Так, а мне что делать?"
  - "Ой, а куда нажать-то?"
  - "Подождите, я не поняла."
take_message:
  - "Хозяина сейчас нет дома, он перезвонит. Что передать?"
before_hangup:
  - "Ой, у меня чайник закипел, я перезвоню."
  - "Кажется, в дверь звонят, извините, мне пора."
  - "Ой, второй телефон звонит, мне надо ответить."
```

- [ ] **Step 4: Add `before_hangup_line()` to DialogEngine**

In `call_agent/dialog_engine.py`, add this method right after `take_message_line`:

```python
    def before_hangup_line(self) -> str:
        return self._pick("before_hangup")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/call_agent/test_dialog_engine.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add call_agent/persona/replies.yaml call_agent/dialog_engine.py tests/call_agent/test_dialog_engine.py
git commit -m "feat(call-agent): add stall fillers and pre-hangup reply line"
```

---

### Task 2: `ScamDetector.leading_score()` — score below threshold

**Files:**
- Modify: `call_agent/scam_detector.py`
- Test: `tests/call_agent/test_scam_detector.py`

**Interfaces:**
- Produces: `ScamDetector.leading_score() -> tuple[str | None, int, int]` — `(scenario_key, score, threshold)` for the highest-scoring scenario so far, even if its score hasn't crossed `threshold`. Returns `(None, 0, 0)` when no scenario has any score yet. Used by Task 4's `CallSession._check_semantically()` and `CallSession.result()`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/call_agent/test_scam_detector.py`:

```python
def test_leading_score_below_threshold():
    d = _detector()
    d.feed("продиктуйте код из смс пожалуйста")   # 60, below 70
    key, score, threshold = d.leading_score()
    assert key == "fake_bank"
    assert score == 60
    assert threshold == 70


def test_leading_score_zero_when_no_hits():
    d = _detector()
    key, score, threshold = d.leading_score()
    assert key is None
    assert score == 0
    assert threshold == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -v`
Expected: FAIL with `AttributeError: 'ScamDetector' object has no attribute 'leading_score'`

- [ ] **Step 3: Add the method**

In `call_agent/scam_detector.py`, add this method to `ScamDetector`, right after `feed`:

```python
    def leading_score(self) -> tuple[str | None, int, int]:
        best_key, best_score, best_threshold = None, 0, 0
        for scenario in self._scenarios:
            score = self._scores[scenario.key]
            if score > best_score:
                best_key, best_score, best_threshold = scenario.key, score, scenario.threshold
        return (best_key, best_score, best_threshold)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add call_agent/scam_detector.py tests/call_agent/test_scam_detector.py
git commit -m "feat(call-agent): add ScamDetector.leading_score for below-threshold scores"
```

---

### Task 3: `call_agent/semantic_check.py` — Ollama yes/no scam check

**Files:**
- Create: `call_agent/semantic_check.py`
- Test: Create `tests/call_agent/test_semantic_check.py`

**Interfaces:**
- Consumes: `settings.ollama_url`, `settings.ollama_model` (existing, `call_agent/config.py`, already used by `call_agent/summary.py`).
- Produces: `check_scam_semantically(transcript: str, settings, http_post=None) -> bool`. Used by Task 5's `_submit_semantic_check` in `call_agent/main.py`, wrapped in a `ThreadPoolExecutor.submit(...)` call — this function itself is plain synchronous code, same shape as `summarize_transcript` in `call_agent/summary.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/call_agent/test_semantic_check.py`:

```python
import call_agent.config as cfg
from call_agent.semantic_check import check_scam_semantically


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
    def json(self):
        return self._payload


def test_returns_true_when_answer_is_da():
    def fake_post(url, json, timeout):
        return FakeResp(200, {"response": "Да, это похоже на мошенничество."})
    assert check_scam_semantically("...", cfg.Settings(), http_post=fake_post) is True


def test_returns_false_when_answer_is_net():
    def fake_post(url, json, timeout):
        return FakeResp(200, {"response": "Нет, обычный разговор."})
    assert check_scam_semantically("...", cfg.Settings(), http_post=fake_post) is False


def test_returns_false_on_error():
    def boom(url, json, timeout):
        raise RuntimeError("ollama down")
    assert check_scam_semantically("...", cfg.Settings(), http_post=boom) is False


def test_returns_false_on_non_200():
    def fake_post(url, json, timeout):
        return FakeResp(500, {})
    assert check_scam_semantically("...", cfg.Settings(), http_post=fake_post) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/call_agent/test_semantic_check.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'call_agent.semantic_check'`

- [ ] **Step 3: Create the module**

Create `call_agent/semantic_check.py`:

```python
"""Real-time semantic scam check via local Ollama. Never raises — fails safe to False."""
from __future__ import annotations

_PROMPT = (
    "Ты определяешь, похож ли телефонный разговор на мошенничество. "
    "Вот разговор до сих пор:\n\n"
)


def check_scam_semantically(transcript: str, settings, http_post=None) -> bool:
    if http_post is None:
        import httpx
        http_post = httpx.post
    try:
        resp = http_post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": _PROMPT + transcript
                    + "\n\nЭто мошенничество? Ответь одним словом: да или нет.",
                "stream": False,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return False
        answer = (resp.json().get("response") or "").strip().lower()
        return answer.startswith("да")
    except Exception:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/call_agent/test_semantic_check.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add call_agent/semantic_check.py tests/call_agent/test_semantic_check.py
git commit -m "feat(call-agent): add Ollama-backed semantic scam check"
```

---

### Task 4: `CallSession` — background-check state machine

**Files:**
- Modify: `call_agent/session.py` (full-file rewrite — nearly every method is touched)
- Test: `tests/call_agent/test_session.py`

**Interfaces:**
- Consumes: `DialogEngine.before_hangup_line()` (Task 1), `ScamDetector.leading_score()` (Task 2). Constructor parameter `check_submitter: Callable[[str], "concurrent.futures.Future[bool]"] | None = None` — in production this is bound in Task 5 to a `ThreadPoolExecutor` running `semantic_check.check_scam_semantically`; in tests, inject a fake returning a manually-controlled `concurrent.futures.Future()`.
- Produces: `CallSession.__init__(..., check_submitter=None)` (new optional kwarg, defaults preserve today's behavior exactly when omitted). `CallSession.result()` now returns `verdict="scam"` with `ended_reason="detected_scam"` when the semantic check (not just the rule-based detector) confirmed a scam.

- [ ] **Step 1: Write the failing tests**

Add to `tests/call_agent/test_session.py` (add `import concurrent.futures` at the top alongside the existing `os, json` import):

```python
import concurrent.futures


def test_ambiguous_score_without_submitter_falls_through_normally():
    s = _session(["продиктуйте код из смс"])   # 60 points, below 70 threshold
    s.start()
    actions = s.on_pcm(b"\x00\x00")
    assert all(a.type != "hangup" for a in actions)
    assert s.result().verdict == "undetermined"


def test_ambiguous_score_triggers_background_check_and_stalls():
    future = concurrent.futures.Future()
    calls = []
    def fake_submit(transcript):
        calls.append(transcript)
        return future

    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec([
        "продиктуйте код из смс", "повторите пожалуйста код",
    ]))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    s = CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder(), check_submitter=fake_submit)
    s.start()

    actions1 = s.on_pcm(b"\x00\x00")
    assert len(calls) == 1
    assert actions1[0].type == "speak"

    actions2 = s.on_pcm(b"\x00\x00")   # still pending -> another filler, no second submit
    assert len(calls) == 1
    assert actions2[0].type == "speak"


def test_semantic_check_confirms_scam_then_hangs_up():
    future = concurrent.futures.Future()
    def fake_submit(transcript):
        return future

    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec([
        "продиктуйте код из смс", "что-нибудь ещё",
    ]))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    s = CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder(), check_submitter=fake_submit)
    s.start()
    s.on_pcm(b"\x00\x00")            # triggers check, returns filler
    future.set_result(True)          # neural net resolves: scam
    actions = s.on_pcm(b"\x00\x00")  # next turn: resolve

    assert actions[0].type == "speak"
    assert actions[0].text in ["Ой, у меня чайник закипел, я перезвоню.",
                               "Кажется, в дверь звонят, извините, мне пора.",
                               "Ой, второй телефон звонит, мне надо ответить."]
    assert actions[1].type == "hangup"
    result = s.result()
    assert result.verdict == "scam"
    assert result.scenario == "fake_bank"
    assert result.ended_reason == "detected_scam"


def test_semantic_check_clears_and_resumes_normal_conversation():
    future = concurrent.futures.Future()
    def fake_submit(transcript):
        return future

    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec([
        "продиктуйте код из смс", "просто болтаю",
    ]))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    s = CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder(), check_submitter=fake_submit)
    s.start()
    s.on_pcm(b"\x00\x00")            # triggers check, returns filler
    future.set_result(False)         # neural net resolves: not scam
    actions = s.on_pcm(b"\x00\x00")  # next turn: resumes normally

    assert all(a.type != "hangup" for a in actions)
    assert actions[0].text in ["Ага… и что?", "Так, а мне что делать?",
                               "Ой, а куда нажать-то?", "Подождите, я не поняла."]
    assert s.result().verdict == "undetermined"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/call_agent/test_session.py -v`
Expected: FAIL — `TypeError: CallSession.__init__() got an unexpected keyword argument 'check_submitter'`

- [ ] **Step 3: Rewrite `call_agent/session.py`**

Replace the full contents of `call_agent/session.py` with:

```python
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

    def _check_semantically(self) -> list[AgentAction] | None:
        if self._pending_check is not None:
            if not self._pending_check.done():
                return [self._emit_agent(self._dialog.filler())]
            is_scam = bool(self._pending_check.result())
            self._pending_check = None
            if is_scam:
                self._semantic_verdict = True
                self._state = CallState.HANGUP
                self._ended_reason = "detected_scam"
                speak = self._emit_agent(self._dialog.before_hangup_line())
                return [speak, AgentAction(type="hangup", wav_path=None, text="")]
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

    def tick(self, not_scam_timeout_sec: int) -> AgentAction | None:
        if self._state == CallState.TALKING and self._elapsed() >= not_scam_timeout_sec:
            self._state = CallState.TAKE_MESSAGE
            self._ended_reason = "took_message"
            return self._emit_agent(self._dialog.take_message_line())
        return None

    def result(self) -> CallResult:
        verdict, scenario, conf = self._detector.verdict()
        if self._semantic_verdict:
            leading_key, score, threshold = self._detector.leading_score()
            conf = min(100, round(score / threshold * 100)) if threshold else 100
            return CallResult("scam", leading_key or "ai_semantic_check", conf, self._ended_reason)
        return CallResult(verdict, scenario, conf, self._ended_reason)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/call_agent/test_session.py -v`
Expected: PASS (8 tests: the 3 pre-existing plus the 5 new ones)

- [ ] **Step 5: Run the full call-agent suite to check nothing broke**

Run: `python -m pytest tests/call_agent/ -v`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add call_agent/session.py tests/call_agent/test_session.py
git commit -m "feat(call-agent): stall on ambiguous score, verify with background Ollama check"
```

---

### Task 5: Wire the background check into `call_agent/main.py`

**Files:**
- Modify: `call_agent/main.py`

**Interfaces:**
- Consumes: `check_scam_semantically` (Task 3), `CallSession(..., check_submitter=...)` (Task 4).
- Produces: nothing consumed by other tasks — this is the last task, it's the live wiring.

- [ ] **Step 1: Add the executor and the submitter function**

In `call_agent/main.py`, add to the imports (near the other stdlib imports, after `import uuid`):

```python
from concurrent.futures import ThreadPoolExecutor
```

And add this import alongside the other `call_agent.*` imports:

```python
from call_agent.semantic_check import check_scam_semantically
```

In `_startup()`, add the executor creation, and extend `canned` to also warm the new `before_hangup` phrases:

```python
@app.on_event("startup")
def _startup():
    _check_call_agent_models()
    app.state.replies = load_replies(settings.replies_path)
    app.state.scenarios = load_scenarios(settings.scenarios_dir)
    app.state.tts = TTSService(settings)
    app.state.semantic_executor = ThreadPoolExecutor(max_workers=2)
    # Pre-synthesize every canned phrase so calls have zero TTS latency.
    canned = (app.state.replies["greeting"] + app.state.replies["fillers"]
              + app.state.replies["keep_talking"] + app.state.replies["take_message"]
              + app.state.replies["before_hangup"])
    app.state.tts.warm_cache(canned)
    from vosk import Model
    app.state.vosk_model = Model(settings.vosk_model_path)
```

Add this module-level function right after `_new_recognizer` (before the `/health` route):

```python
def _submit_semantic_check(transcript: str):
    return app.state.semantic_executor.submit(check_scam_semantically, transcript, settings)
```

- [ ] **Step 2: Pass the submitter into `CallSession`**

In `ws_call()`, change:

```python
    session = CallSession(call_id, asr, detector, dialog, app.state.tts, recorder,
                          on_event=on_event)
```

to:

```python
    session = CallSession(call_id, asr, detector, dialog, app.state.tts, recorder,
                          on_event=on_event, check_submitter=_submit_semantic_check)
```

- [ ] **Step 3: Run the full call-agent suite**

Run: `python -m pytest tests/call_agent/ -v`
Expected: PASS (all tests — this task has no new automated tests of its own; it's pure wiring covered by Task 4's tests plus the manual check below)

- [ ] **Step 4: Rebuild and restart call-agent**

```bash
docker compose build api && docker compose build call-agent && docker compose up -d call-agent
```

- [ ] **Step 5: Manual end-to-end verification**

Open the call-agent browser simulator (http://localhost:4000/simulator), start a call, and say a phrase that scores partial points without crossing threshold — e.g. **"продиктуйте код из смс"** alone (60 points, fake_bank threshold is 70).

Confirm:
- The agent responds with a stall filler (e.g. "Сейчас-сейчас, минуточку…") instead of a normal reply.
- If you keep talking before Ollama answers, you keep getting fillers (check `docker compose logs call-agent --tail 50` for confirmation the check is still pending, not resubmitted).
- Eventually the agent either resumes the conversation normally (if Ollama judged it not a scam) or says a pre-hangup line and hangs up (if Ollama judged it a scam) — both are valid outcomes since this is the real model's judgment, not scripted.

- [ ] **Step 6: Commit**

```bash
git add call_agent/main.py
git commit -m "feat(call-agent): wire background semantic scam check into the live call"
```

---

## Self-Review Notes

- **Spec coverage:** trigger condition (0 < score < threshold) → Task 4's `_check_semantically`; stall behavior while pending → Task 4 tests; at most one check per call → Task 4 test (`test_ambiguous_score_triggers_background_check_and_stalls` asserts `len(calls) == 1` across two turns); confirmed-scam → pre-hangup line + auto hangup → Task 4 test; not-scam → resumes normally → Task 4 test; Ollama failure/timeout → fails safe to `False` → Task 3 tests; new phrases (fillers + before_hangup) → Task 1; `CallSession` stays synchronous/testable via injected `check_submitter` → Task 4 uses `concurrent.futures.Future` directly, no real threads in tests; reuse of existing `ollama_url`/`ollama_model` → Task 3, no new config. All spec sections have a task.
- **Placeholder scan:** no TBD/TODO; every step has literal code, exact test assertions, and exact commands.
- **Type consistency:** `ScamDetector.leading_score()` (Task 2) returns `(str | None, int, int)`, consumed identically in Task 4's `_check_semantically` (`_, score, threshold = ...`) and `result()` (`leading_key, score, threshold = ...`). `DialogEngine.before_hangup_line()` (Task 1) name matches its one call site in Task 4. `check_scam_semantically(transcript, settings, http_post=None)` (Task 3) signature matches its one call site in Task 5's `_submit_semantic_check`. `CallSession(..., check_submitter=None)` keyword name is identical across Task 4's constructor and Task 5's `CallSession(...)` call site.
- **Verdict/DB correctness check:** `CallSession.result()` was updated so a semantic-check-confirmed scam reports `verdict="scam"` (not `"undetermined"`, which is what the plain rule-based detector would still say on its own, since the score never crossed threshold by rule alone) — this matters because `call_agent/main.py:_finalize()` reads `result.verdict` to decide `ended_reason` and to persist the call's final verdict to the database; without this, an AI-confirmed scam would be silently recorded as "undetermined" in Postgres and in the n8n/Telegram alert payload from the earlier feature.
