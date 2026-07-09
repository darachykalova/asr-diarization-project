# Anti-Scam Voice Agent — Stage 1 (Browser Prototype) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new `call-agent` service that answers a simulated phone call from the browser, transcribes the caller in real time with Vosk, decides "scam / not scam" via YAML rule scenarios, replies with a cached Silero voice, records the call, and after hangup runs the existing Whisper pipeline plus an Ollama summary — all visible in a new "Звонки" (Calls) admin tab.

**Architecture:** A new Docker container (`call-agent`, same `asr-app` image family, own entrypoint) hosts a FastAPI app with one WebSocket endpoint. Inside, a `CallSession` orchestrates four pure-ish components: `StreamingASR` (Vosk), `ScamDetector` (YAML rules), `DialogEngine` (state machine + YAML replies), `TTSService` (Silero, WAV cache). The browser captures microphone PCM, streams 16 kHz Int16 chunks over the WebSocket, and plays back the agent's audio replies. Call metadata/events go to the existing PostgreSQL; the recording goes to the existing MinIO and triggers the existing Whisper `build_pipeline_chain`. The admin API and React frontend gain a Calls list + detail view reusing existing auth/pagination patterns.

**Tech Stack:** Python 3.12, FastAPI, `vosk`, `torch` + Silero TTS (v4_ru), SQLAlchemy (existing), MinIO client (existing), Celery chain (existing), Ollama (HTTP, local), React + TypeScript + Vite + Tailwind (existing frontend), pytest.

## Global Constraints

- Python 3.12; base image `python:3.12-slim` (matches existing `Dockerfile`).
- **Do NOT modify pipeline files:** `tasks/audio_tasks.py`, `tasks/pipeline_tasks.py`, `services/model_cache.py`, `services/model_registry.py`, `services/chunking_service.py`. The call-agent *calls* `build_pipeline_chain(...)` but never edits it.
- Runtime is fully offline: `HF_HUB_OFFLINE=1`. Vosk and Silero model files are baked/mounted, never downloaded at runtime. Ollama runs as a local container.
- Passwords/JWT: reuse existing `api/auth_users.py`; the Calls admin routes are protected by `Depends(get_current_user)` exactly like `api/routes/admin_audio.py`.
- Audit: revealing a call transcript writes to the existing audit log (Constitution Principle VI). Audit records never contain transcript text.
- DB access lives in `database/crud.py` (project rule: no `repository.py`). New tables added to `database/models.py`.
- Respond to the user in Russian (project preference); code comments/docstrings in the language matching surrounding files (mixed RU/EN is fine, follow the file being edited).
- Reuse `clients/minio_client.py:MinioStorageClient` (`upload_file(local_path, object_key, content_type)`, `download_file(object_key, local_path)`), and `crud.create_job(db, job_id, status, audio_key, params)`.

## File Structure

```
call_agent/                         # NEW Python package — the whole service
├─ __init__.py
├─ main.py                          # FastAPI app, WebSocket endpoint, CORS
├─ config.py                        # env-driven settings (model paths, thresholds)
├─ session.py                       # CallSession orchestrator + CallState enum
├─ streaming_asr.py                 # Vosk wrapper (StreamingASR)
├─ scam_detector.py                 # ScamDetector + Scenario loader
├─ dialog_engine.py                 # DialogEngine state machine + reply loader
├─ tts_service.py                   # Silero wrapper + WAV cache (TTSService)
├─ recorder.py                      # CallRecorder (WAV write + MinIO + Job)
├─ summary.py                       # Ollama summary client (post-call)
├─ scenarios/                       # YAML scam scenarios (data, not code)
│  ├─ fake_bank.yaml
│  ├─ gas_service.yaml
│  └─ police.yaml
└─ persona/
   └─ replies.yaml                  # agent reply phrases + fillers

call_agent/Dockerfile               # NEW image for the service
tests/call_agent/                   # NEW tests
├─ __init__.py
├─ test_scam_detector.py
├─ test_dialog_engine.py
├─ test_tts_service.py
├─ test_streaming_asr.py
├─ test_session.py
├─ test_recorder.py
├─ test_calls_crud.py
└─ test_admin_calls.py

database/models.py                  # MODIFY: add Call, CallEvent tables
database/crud.py                    # MODIFY: add call CRUD functions
api/routes/admin_calls.py           # NEW: admin Calls list/detail routes
api/routes/admin_router.py          # MODIFY: include admin_calls_router

frontend/src/pages/CallsListPage.tsx    # NEW
frontend/src/pages/CallDetailPage.tsx   # NEW
frontend/src/pages/CallSimulatorPage.tsx# NEW (browser mic test harness)
frontend/src/components/Nav.tsx         # MODIFY: add "Звонки" + "Симулятор"
frontend/src/App.tsx                    # MODIFY: add routes

docker-compose.yml                  # MODIFY: add call-agent + ollama services
```

**Phasing (each phase = shippable, testable increment):**
- **Phase 1 — Offline brain:** `ScamDetector`, `DialogEngine`, scenarios/replies. Pure logic, 100% unit-tested, no models/containers. (Tasks 1–3)
- **Phase 2 — Voice I/O:** `TTSService` (Silero), `StreamingASR` (Vosk), config. (Tasks 4–6)
- **Phase 3 — Persistence:** `Call`/`CallEvent` models + crud. (Tasks 7–8)
- **Phase 4 — Orchestration:** `CallRecorder`, `CallSession`, post-call `summary`. (Tasks 9–11)
- **Phase 5 — Service + wiring:** FastAPI WebSocket app, Dockerfile, compose. (Tasks 12–13)
- **Phase 6 — Admin API + frontend:** Calls routes, list/detail pages, simulator page, nav/routes. (Tasks 14–18)

---

## Phase 1 — Offline Brain

### Task 1: Scenario data files + ScamDetector

**Files:**
- Create: `call_agent/__init__.py` (empty)
- Create: `call_agent/scenarios/fake_bank.yaml`
- Create: `call_agent/scenarios/gas_service.yaml`
- Create: `call_agent/scenarios/police.yaml`
- Create: `call_agent/scam_detector.py`
- Test: `tests/call_agent/__init__.py` (empty), `tests/call_agent/test_scam_detector.py`

**Interfaces:**
- Produces:
  - `Scenario` dataclass: `name: str`, `key: str`, `threshold: int`, `triggers: list[Trigger]` where `Trigger` has `phrases: list[str]`, `weight: int`.
  - `load_scenarios(dir_path: str) -> list[Scenario]`
  - `class ScamDetector`:
    - `__init__(self, scenarios: list[Scenario])`
    - `feed(self, text: str) -> list[Hit]` — lowercases `text`, finds trigger phrase substrings, accumulates per-scenario score, returns newly matched `Hit`s this call. `Hit` = dataclass `scenario_key: str`, `phrase: str`, `weight: int`.
    - `verdict(self) -> tuple[str, str | None, int]` — returns `(verdict, scenario_key, confidence)` where verdict ∈ `{"scam","undetermined"}`; scenario_key is the highest-scoring scenario at/over threshold (or None); confidence = `min(100, round(score / threshold * 100))` for that scenario (0 if none).
    - `total_delta_for(self, text: str) -> int` — convenience: sum of weights newly added by feeding `text` (used by CallEvent.scam_delta). NOTE: `feed` already returns hits; `scam_delta` for an event = `sum(h.weight for h in feed(text))`.

- [ ] **Step 1: Write scenario YAML files**

`call_agent/scenarios/fake_bank.yaml`:
```yaml
key: fake_bank
name: Фейковый банк
threshold: 70
triggers:
  - phrases: ["служба безопасности", "безопасности банка"]
    weight: 40
  - phrases: ["карта заблокирована", "заблокирована карта", "подозрительная операция"]
    weight: 30
  - phrases: ["продиктуйте код", "код из смс", "назовите код", "код из сообщения"]
    weight: 60
  - phrases: ["оформлен кредит", "кто-то оформил", "заявка на кредит"]
    weight: 35
```

`call_agent/scenarios/gas_service.yaml`:
```yaml
key: gas_service
name: Газовая служба
threshold: 70
triggers:
  - phrases: ["газовая служба", "горгаз", "газовое оборудование"]
    weight: 40
  - phrases: ["проверка оборудования", "замена счётчика", "поверка счётчика"]
    weight: 35
  - phrases: ["впустите мастера", "откройте дверь", "мастер придёт"]
    weight: 40
  - phrases: ["штраф", "отключим газ", "отключение газа"]
    weight: 30
```

`call_agent/scenarios/police.yaml`:
```yaml
key: police
name: Полиция / следователь
threshold: 70
triggers:
  - phrases: ["следственный комитет", "следователь", "уголовное дело", "мвд"]
    weight: 45
  - phrases: ["на вас оформлен", "мошенники пытаются", "перевод на безопасный счёт"]
    weight: 45
  - phrases: ["не кладите трубку", "никому не говорите", "подписка о неразглашении"]
    weight: 35
  - phrases: ["декларируйте средства", "задекларируйте", "содействие следствию"]
    weight: 30
```

- [ ] **Step 2: Write the failing tests**

`tests/call_agent/test_scam_detector.py`:
```python
import os
from call_agent.scam_detector import load_scenarios, ScamDetector

SCEN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "call_agent", "scenarios")


def _detector():
    return ScamDetector(load_scenarios(SCEN_DIR))


def test_loads_three_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {"fake_bank", "gas_service", "police"}


def test_clean_call_is_undetermined():
    d = _detector()
    d.feed("привет это мама как дела")
    verdict, scenario, conf = d.verdict()
    assert verdict == "undetermined"
    assert scenario is None
    assert conf == 0


def test_bank_scam_crosses_threshold():
    d = _detector()
    d.feed("здравствуйте это служба безопасности банка")   # 40
    d.feed("ваша карта заблокирована")                       # +30 = 70
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "fake_bank"
    assert conf == 100


def test_single_strong_phrase_enough():
    d = _detector()
    hits = d.feed("продиктуйте код из смс пожалуйста")        # 60, below 70
    assert any(h.phrase == "продиктуйте код" for h in hits)
    assert d.verdict()[0] == "undetermined"


def test_case_insensitive_and_delta():
    d = _detector()
    delta = sum(h.weight for h in d.feed("СЛУЖБА БЕЗОПАСНОСТИ банка"))
    assert delta == 40


def test_phrase_counted_once_per_feed_but_accumulates_across_feeds():
    d = _detector()
    d.feed("служба безопасности")   # 40
    d.feed("служба безопасности")   # +40 = 80 -> scam
    assert d.verdict()[0] == "scam"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'call_agent.scam_detector'`

- [ ] **Step 4: Implement `call_agent/scam_detector.py`**

```python
"""Rule-based scam detection over YAML scenarios. Pure logic, offline."""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field

import yaml


@dataclass
class Trigger:
    phrases: list[str]
    weight: int


@dataclass
class Scenario:
    key: str
    name: str
    threshold: int
    triggers: list[Trigger]


@dataclass
class Hit:
    scenario_key: str
    phrase: str
    weight: int


def load_scenarios(dir_path: str) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for path in sorted(glob.glob(os.path.join(dir_path, "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        triggers = [Trigger(phrases=[p.lower() for p in t["phrases"]], weight=int(t["weight"]))
                    for t in raw["triggers"]]
        scenarios.append(Scenario(
            key=raw["key"], name=raw["name"],
            threshold=int(raw["threshold"]), triggers=triggers,
        ))
    return scenarios


class ScamDetector:
    def __init__(self, scenarios: list[Scenario]):
        self._scenarios = scenarios
        self._scores: dict[str, int] = {s.key: 0 for s in scenarios}

    def feed(self, text: str) -> list[Hit]:
        low = text.lower()
        hits: list[Hit] = []
        for scenario in self._scenarios:
            for trig in scenario.triggers:
                matched = next((p for p in trig.phrases if p in low), None)
                if matched is not None:
                    self._scores[scenario.key] += trig.weight
                    hits.append(Hit(scenario.key, matched, trig.weight))
        return hits

    def verdict(self) -> tuple[str, str | None, int]:
        best_key, best_conf = None, 0
        for scenario in self._scenarios:
            score = self._scores[scenario.key]
            if score >= scenario.threshold:
                conf = min(100, round(score / scenario.threshold * 100))
                if conf > best_conf or (conf == best_conf and best_key is None):
                    best_key, best_conf = scenario.key, conf
        if best_key is None:
            return ("undetermined", None, 0)
        return ("scam", best_key, best_conf)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/call_agent/test_scam_detector.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Commit**

```bash
git add call_agent/__init__.py call_agent/scenarios call_agent/scam_detector.py tests/call_agent/__init__.py tests/call_agent/test_scam_detector.py
git commit -m "feat(call-agent): rule-based scam detector with YAML scenarios"
```

---

### Task 2: Reply data + DialogEngine state machine

**Files:**
- Create: `call_agent/persona/replies.yaml`
- Create: `call_agent/dialog_engine.py`
- Test: `tests/call_agent/test_dialog_engine.py`

**Interfaces:**
- Consumes: nothing from Task 1 (independent).
- Produces:
  - `class DialogEngine`:
    - `__init__(self, replies: dict, rng=random.Random())` — `replies` loaded from YAML with keys `greeting`, `fillers`, `keep_talking`, `take_message`.
    - `load_replies(path: str) -> dict` (module function)
    - `greeting(self) -> str` — a greeting phrase.
    - `on_caller_utterance(self, text: str, verdict: str) -> Reply` — returns a `Reply` dataclass `text: str`, `kind: str`, `hang_up: bool`. Logic: if `verdict == "scam"` → `take_message`?? No — scam ⇒ terminate. Return `Reply(text="", kind="hangup", hang_up=True)` with no spoken line. If text contains a greeting word ("здравствуйте","алло","добрый") and engine hasn't greeted content yet → a `keep_talking` line. Otherwise → a `keep_talking` line. (Filler selection is a separate method used by the session while waiting.)
    - `filler(self) -> str` — a random filler phrase (used to mask latency).
    - `take_message_line(self) -> str` — the "оставьте сообщение" line, used when the not-scam timeout fires.
  - `Reply` dataclass: `text: str`, `kind: str` (`"talk" | "hangup"`), `hang_up: bool`.

- [ ] **Step 1: Write `call_agent/persona/replies.yaml`**

```yaml
greeting:
  - "Алло?"
  - "Да, слушаю вас."
fillers:
  - "Сейчас-сейчас, минуточку…"
  - "А? Повторите, пожалуйста."
  - "Ой, подождите, очки найду."
  - "Кхм… кхм…"
keep_talking:
  - "Ага… и что?"
  - "Так, а мне что делать?"
  - "Ой, а куда нажать-то?"
  - "Подождите, я не поняла."
take_message:
  - "Хозяина сейчас нет дома, он перезвонит. Что передать?"
```

- [ ] **Step 2: Write the failing tests**

`tests/call_agent/test_dialog_engine.py`:
```python
import os
import random
from call_agent.dialog_engine import DialogEngine, load_replies

REPLIES = os.path.join(os.path.dirname(__file__), "..", "..", "call_agent", "persona", "replies.yaml")


def _engine():
    return DialogEngine(load_replies(REPLIES), rng=random.Random(0))


def test_greeting_from_pool():
    e = _engine()
    assert e.greeting() in ["Алло?", "Да, слушаю вас."]


def test_scam_verdict_triggers_hangup_with_no_line():
    e = _engine()
    reply = e.on_caller_utterance("продиктуйте код из смс", verdict="scam")
    assert reply.hang_up is True
    assert reply.kind == "hangup"
    assert reply.text == ""


def test_undetermined_keeps_talking():
    e = _engine()
    reply = e.on_caller_utterance("а что случилось", verdict="undetermined")
    assert reply.hang_up is False
    assert reply.kind == "talk"
    assert reply.text in ["Ага… и что?", "Так, а мне что делать?",
                          "Ой, а куда нажать-то?", "Подождите, я не поняла."]


def test_filler_from_pool():
    e = _engine()
    assert e.filler() in ["Сейчас-сейчас, минуточку…", "А? Повторите, пожалуйста.",
                          "Ой, подождите, очки найду.", "Кхм… кхм…"]


def test_take_message_line():
    e = _engine()
    assert e.take_message_line() == "Хозяина сейчас нет дома, он перезвонит. Что передать?"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/call_agent/test_dialog_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'call_agent.dialog_engine'`

- [ ] **Step 4: Implement `call_agent/dialog_engine.py`**

```python
"""Deterministic reply selection. No NLU — keyword + verdict driven."""
from __future__ import annotations

import random
from dataclasses import dataclass

import yaml


@dataclass
class Reply:
    text: str
    kind: str      # "talk" | "hangup"
    hang_up: bool


def load_replies(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class DialogEngine:
    def __init__(self, replies: dict, rng: random.Random | None = None):
        self._replies = replies
        self._rng = rng or random.Random()

    def _pick(self, key: str) -> str:
        return self._rng.choice(self._replies[key])

    def greeting(self) -> str:
        return self._pick("greeting")

    def filler(self) -> str:
        return self._pick("fillers")

    def take_message_line(self) -> str:
        return self._pick("take_message")

    def on_caller_utterance(self, text: str, verdict: str) -> Reply:
        if verdict == "scam":
            return Reply(text="", kind="hangup", hang_up=True)
        return Reply(text=self._pick("keep_talking"), kind="talk", hang_up=False)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/call_agent/test_dialog_engine.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add call_agent/persona/replies.yaml call_agent/dialog_engine.py tests/call_agent/test_dialog_engine.py
git commit -m "feat(call-agent): dialog engine state machine with YAML replies"
```

---

### Task 3: Config module

**Files:**
- Create: `call_agent/config.py`
- Test: `tests/call_agent/test_config.py`

**Interfaces:**
- Produces: `class Settings` (plain class, env-driven) with attributes:
  - `vosk_model_path: str` (env `VOSK_MODEL_PATH`, default `/app/models/vosk/vosk-model-small-ru-0.22`)
  - `silero_model_path: str` (env `SILERO_MODEL_PATH`, default `/app/models/silero/v4_ru.pt`)
  - `silero_speaker: str` (env `SILERO_SPEAKER`, default `baya`)
  - `tts_sample_rate: int` (env `TTS_SAMPLE_RATE`, default `48000`)
  - `scenarios_dir: str` (default `<package>/scenarios`)
  - `replies_path: str` (default `<package>/persona/replies.yaml`)
  - `not_scam_timeout_sec: int` (env `NOT_SCAM_TIMEOUT_SEC`, default `180`)
  - `ollama_url: str` (env `OLLAMA_URL`, default `http://ollama:11434`)
  - `ollama_model: str` (env `OLLAMA_MODEL`, default `qwen2.5:3b`)
  - `tts_cache_dir: str` (env `TTS_CACHE_DIR`, default `/app/data/tts_cache`)
  - `get_settings() -> Settings` (module-level singleton).

- [ ] **Step 1: Write the failing test**

`tests/call_agent/test_config.py`:
```python
import importlib


def test_defaults(monkeypatch):
    for var in ["VOSK_MODEL_PATH", "SILERO_SPEAKER", "NOT_SCAM_TIMEOUT_SEC"]:
        monkeypatch.delenv(var, raising=False)
    import call_agent.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.silero_speaker == "baya"
    assert s.not_scam_timeout_sec == 180
    assert s.scenarios_dir.endswith("scenarios")


def test_env_override(monkeypatch):
    monkeypatch.setenv("SILERO_SPEAKER", "xenia")
    monkeypatch.setenv("NOT_SCAM_TIMEOUT_SEC", "90")
    import call_agent.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.silero_speaker == "xenia"
    assert s.not_scam_timeout_sec == 90
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/call_agent/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'call_agent.config'`

- [ ] **Step 3: Implement `call_agent/config.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/call_agent/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add call_agent/config.py tests/call_agent/test_config.py
git commit -m "feat(call-agent): env-driven config module"
```

---

## Phase 2 — Voice I/O

### Task 4: TTSService (Silero + WAV cache)

**Files:**
- Create: `call_agent/tts_service.py`
- Test: `tests/call_agent/test_tts_service.py`

**Interfaces:**
- Consumes: `call_agent.config.Settings`.
- Produces:
  - `class TTSService`:
    - `__init__(self, settings, model=None)` — if `model` is None, lazy-loads Silero from `settings.silero_model_path` on first `synthesize`. Tests inject a fake `model` with `.apply_tts(text, speaker, sample_rate) -> torch-like tensor` — to keep tests torch-free, the fake returns a numpy `float32` array and `synthesize` must accept anything array-like.
    - `synthesize(self, text: str) -> str` — returns a filesystem path to a 16 kHz mono Int16 WAV. Caches by `sha1(text+speaker+rate)` in `settings.tts_cache_dir`; a cache hit skips the model call. Silero outputs `tts_sample_rate` (48k) float32 → resample to 16k Int16 for the phone-quality stream and WAV.
    - `warm_cache(self, phrases: list[str]) -> None` — pre-synthesizes a list (used at startup for greetings/fillers).

- [ ] **Step 1: Write the failing test**

`tests/call_agent/test_tts_service.py`:
```python
import os
import wave
import numpy as np
import call_agent.config as cfg
from call_agent.tts_service import TTSService


class FakeModel:
    def __init__(self):
        self.calls = 0
    def apply_tts(self, text, speaker, sample_rate):
        self.calls += 1
        # 0.5s of silence at the requested rate, float32 in [-1, 1]
        return np.zeros(int(sample_rate * 0.5), dtype=np.float32)


def _service(tmp_path, model):
    s = cfg.Settings()
    s.tts_cache_dir = str(tmp_path)
    return TTSService(s, model=model)


def test_synthesize_writes_16k_mono_int16_wav(tmp_path):
    svc = _service(tmp_path, FakeModel())
    path = svc.synthesize("привет")
    assert os.path.exists(path)
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2


def test_cache_hit_skips_model(tmp_path):
    model = FakeModel()
    svc = _service(tmp_path, model)
    svc.synthesize("одна фраза")
    svc.synthesize("одна фраза")
    assert model.calls == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/call_agent/test_tts_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'call_agent.tts_service'`

- [ ] **Step 3: Implement `call_agent/tts_service.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/call_agent/test_tts_service.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add call_agent/tts_service.py tests/call_agent/test_tts_service.py
git commit -m "feat(call-agent): Silero TTS service with WAV cache"
```

---

### Task 5: StreamingASR (Vosk wrapper)

**Files:**
- Create: `call_agent/streaming_asr.py`
- Test: `tests/call_agent/test_streaming_asr.py`

**Interfaces:**
- Consumes: `call_agent.config.Settings`.
- Produces:
  - `class StreamingASR`:
    - `__init__(self, settings, recognizer=None)` — if `recognizer` is None, lazy-builds a Vosk `KaldiRecognizer` from `settings.vosk_model_path` at 16 kHz on first `accept`. Tests inject a fake recognizer.
    - `accept(self, pcm_bytes: bytes) -> dict` — feeds Int16LE PCM. Returns `{"final": "<text>"}` when Vosk reports an utterance boundary (`AcceptWaveform` True), else `{"partial": "<text>"}`.
    - `flush(self) -> str` — returns the final residual text (`FinalResult`).
  - Fake recognizer contract (for tests): object with `AcceptWaveform(bytes) -> bool`, `Result() -> str(json)`, `PartialResult() -> str(json)`, `FinalResult() -> str(json)`.

- [ ] **Step 1: Write the failing test**

`tests/call_agent/test_streaming_asr.py`:
```python
import json
import call_agent.config as cfg
from call_agent.streaming_asr import StreamingASR


class FakeRec:
    def __init__(self, script):
        # script: list of (is_final, text)
        self._script = script
        self._i = 0
    def AcceptWaveform(self, data):
        is_final, _ = self._script[self._i]
        return is_final
    def Result(self):
        _, text = self._script[self._i]; self._i += 1
        return json.dumps({"text": text})
    def PartialResult(self):
        _, text = self._script[self._i]; self._i += 1
        return json.dumps({"partial": text})
    def FinalResult(self):
        return json.dumps({"text": "хвост"})


def test_partial_then_final():
    rec = FakeRec([(False, "служба"), (True, "служба безопасности")])
    asr = StreamingASR(cfg.Settings(), recognizer=rec)
    assert asr.accept(b"\x00\x00") == {"partial": "служба"}
    assert asr.accept(b"\x00\x00") == {"final": "служба безопасности"}


def test_flush_returns_residual():
    rec = FakeRec([])
    asr = StreamingASR(cfg.Settings(), recognizer=rec)
    assert asr.flush() == "хвост"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/call_agent/test_streaming_asr.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'call_agent.streaming_asr'`

- [ ] **Step 3: Implement `call_agent/streaming_asr.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/call_agent/test_streaming_asr.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add call_agent/streaming_asr.py tests/call_agent/test_streaming_asr.py
git commit -m "feat(call-agent): Vosk streaming ASR wrapper"
```

---

### Task 6: Ollama summary client

**Files:**
- Create: `call_agent/summary.py`
- Test: `tests/call_agent/test_summary.py`

**Interfaces:**
- Consumes: `call_agent.config.Settings`.
- Produces:
  - `summarize_transcript(full_text: str, settings, http_post=None) -> str | None` — POSTs to `{ollama_url}/api/generate` with `{"model": ..., "prompt": <ru prompt + full_text>, "stream": false}`, returns the `response` string. On any exception or non-200, returns `None` (never raises — summary failure must not lose the call). `http_post` is injectable for tests (defaults to `httpx.post`).

- [ ] **Step 1: Write the failing test**

`tests/call_agent/test_summary.py`:
```python
import call_agent.config as cfg
from call_agent.summary import summarize_transcript


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
    def json(self):
        return self._payload


def test_returns_response_text():
    def fake_post(url, json, timeout):
        return FakeResp(200, {"response": "Звонили из банка, требовали код."})
    out = summarize_transcript("...", cfg.Settings(), http_post=fake_post)
    assert out == "Звонили из банка, требовали код."


def test_returns_none_on_error():
    def boom(url, json, timeout):
        raise RuntimeError("ollama down")
    assert summarize_transcript("...", cfg.Settings(), http_post=boom) is None


def test_returns_none_on_non_200():
    def fake_post(url, json, timeout):
        return FakeResp(500, {})
    assert summarize_transcript("...", cfg.Settings(), http_post=fake_post) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/call_agent/test_summary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'call_agent.summary'`

- [ ] **Step 3: Implement `call_agent/summary.py`**

```python
"""Post-call summary via local Ollama. Never raises — returns None on failure."""
from __future__ import annotations

_PROMPT = (
    "Ты помощник, который кратко пересказывает телефонный разговор на русском языке. "
    "Опиши в 2-3 предложениях, о чём был звонок, кто звонил и что просили. "
    "Вот расшифровка разговора:\n\n"
)


def summarize_transcript(full_text: str, settings, http_post=None) -> str | None:
    if http_post is None:
        import httpx
        http_post = httpx.post
    try:
        resp = http_post(
            f"{settings.ollama_url}/api/generate",
            json={"model": settings.ollama_model, "prompt": _PROMPT + full_text, "stream": False},
            timeout=120,
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("response")
    except Exception:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/call_agent/test_summary.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add call_agent/summary.py tests/call_agent/test_summary.py
git commit -m "feat(call-agent): Ollama post-call summary client"
```

---

## Phase 3 — Persistence

### Task 7: Call + CallEvent models

**Files:**
- Modify: `database/models.py` (append two classes at end of file)
- Test: `tests/call_agent/test_calls_crud.py` (model import part)

**Interfaces:**
- Produces (SQLAlchemy models, same style as existing `Job`):
  - `Call`: `id: str` PK (UUID str), `source: str`, `started_at: datetime`, `ended_at: datetime|None`, `duration_sec: float|None`, `verdict: str` default `"undetermined"`, `scenario: str|None`, `confidence: int` default `0`, `ended_reason: str|None`, `job_id: str|None` FK→`jobs.id`, `summary: str|None` Text, `audio_key: str|None`. Index on `started_at`, `verdict`.
  - `CallEvent`: `id: int` PK, `call_id: str` FK→`calls.id` indexed, `at: float` (seconds from call start), `speaker: str` (`"caller"|"agent"`), `text: str` Text, `scam_delta: int` default `0`.

- [ ] **Step 1: Add models to `database/models.py`**

Append (imports `Float`, `String`, `Integer`, `Text`, `DateTime`, `ForeignKey`, `Index` already present):
```python
class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_calls_started_at", "started_at"),
        Index("ix_calls_verdict", "verdict"),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    source: Mapped[str] = mapped_column(String(200), default="browser")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[str] = mapped_column(String(30), default="undetermined")
    scenario: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    ended_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_key: Mapped[str | None] = mapped_column(String(500), nullable=True)


class CallEvent(Base):
    __tablename__ = "call_events"
    __table_args__ = (
        Index("ix_call_events_call_id", "call_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.id"), nullable=False)
    at: Mapped[float] = mapped_column(Float, default=0.0)
    speaker: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    scam_delta: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 2: Write a smoke test that the tables create**

`tests/call_agent/test_calls_crud.py` (first test only for now):
```python
from database.database import Base
from database.models import Call, CallEvent


def test_call_models_registered():
    assert "calls" in Base.metadata.tables
    assert "call_events" in Base.metadata.tables
```

- [ ] **Step 3: Run test**

Run: `python -m pytest tests/call_agent/test_calls_crud.py::test_call_models_registered -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add database/models.py tests/call_agent/test_calls_crud.py
git commit -m "feat(call-agent): Call and CallEvent DB models"
```

---

### Task 8: Call CRUD functions

**Files:**
- Modify: `database/crud.py` (append a "Calls" section, mirroring existing style)
- Test: `tests/call_agent/test_calls_crud.py` (extend)

**Interfaces:**
- Consumes: `Call`, `CallEvent` from Task 7.
- Produces (all take `db: Session`):
  - `create_call(db, call_id, source, started_at) -> Call`
  - `add_call_event(db, call_id, at, speaker, text, scam_delta=0) -> CallEvent`
  - `finalize_call(db, call_id, ended_at, duration_sec, verdict, scenario, confidence, ended_reason, job_id, audio_key) -> Call | None`
  - `set_call_summary(db, call_id, summary) -> Call | None`
  - `list_calls(db, page=1, page_size=20, verdict=None, scenario=None, date_from=None, date_to=None) -> dict` — same envelope as `list_audio`: `{items, page, page_size, total, pages}`; each item = `{call_id, source, started_at, duration_sec, verdict, scenario, confidence}`.
  - `get_call_detail(db, call_id) -> dict | None` — `{call: {...all fields...}, events: [{at, speaker, text, scam_delta}, ...]}` ordered by `at`.

- [ ] **Step 1: Write failing tests (extend `tests/call_agent/test_calls_crud.py`)**

```python
from datetime import datetime, timedelta
from database.session import SessionLocal
from database import crud


def test_create_and_finalize_call():
    db = SessionLocal()
    try:
        cid = "call-test-1"
        crud.create_call(db, cid, source="browser", started_at=datetime.utcnow())
        crud.add_call_event(db, cid, at=1.0, speaker="caller", text="служба безопасности", scam_delta=40)
        crud.add_call_event(db, cid, at=2.0, speaker="agent", text="алло", scam_delta=0)
        crud.finalize_call(db, cid, ended_at=datetime.utcnow(), duration_sec=12.0,
                           verdict="scam", scenario="fake_bank", confidence=100,
                           ended_reason="detected_scam", job_id=None, audio_key="calls/x.wav")
        detail = crud.get_call_detail(db, cid)
        assert detail["call"]["verdict"] == "scam"
        assert detail["call"]["confidence"] == 100
        assert len(detail["events"]) == 2
        assert detail["events"][0]["speaker"] == "caller"
    finally:
        db.query(crud.CallEvent).filter_by(call_id="call-test-1").delete()
        db.query(crud.Call).filter_by(id="call-test-1").delete()
        db.commit()
        db.close()


def test_list_calls_filters_by_verdict():
    db = SessionLocal()
    try:
        crud.create_call(db, "call-scam", "browser", datetime.utcnow())
        crud.finalize_call(db, "call-scam", datetime.utcnow(), 5.0, "scam",
                           "fake_bank", 90, "detected_scam", None, "k")
        page = crud.list_calls(db, verdict="scam")
        assert any(i["call_id"] == "call-scam" for i in page["items"])
        assert all(i["verdict"] == "scam" for i in page["items"])
    finally:
        db.query(crud.Call).filter_by(id="call-scam").delete()
        db.commit()
        db.close()
```
(Note: `crud.Call`/`crud.CallEvent` must be importable — ensure `database/crud.py` imports them from `database.models`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/call_agent/test_calls_crud.py -v`
Expected: FAIL with `AttributeError: module 'database.crud' has no attribute 'create_call'`

- [ ] **Step 3: Implement the Calls section in `database/crud.py`**

Ensure `Call, CallEvent` are in the models import at the top of `crud.py`, then append:
```python
# ---------------------------------------------------------------------------
# Calls (anti-scam agent)
# ---------------------------------------------------------------------------

def create_call(db: Session, call_id: str, source: str, started_at) -> Call:
    call = Call(id=call_id, source=source, started_at=started_at)
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def add_call_event(db: Session, call_id: str, at: float, speaker: str,
                   text: str, scam_delta: int = 0) -> CallEvent:
    ev = CallEvent(call_id=call_id, at=at, speaker=speaker, text=text, scam_delta=scam_delta)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def finalize_call(db: Session, call_id: str, ended_at, duration_sec, verdict,
                  scenario, confidence, ended_reason, job_id, audio_key) -> Call | None:
    call = db.query(Call).filter(Call.id == call_id).first()
    if call is None:
        return None
    call.ended_at = ended_at
    call.duration_sec = duration_sec
    call.verdict = verdict
    call.scenario = scenario
    call.confidence = confidence
    call.ended_reason = ended_reason
    call.job_id = job_id
    call.audio_key = audio_key
    db.commit()
    db.refresh(call)
    return call


def set_call_summary(db: Session, call_id: str, summary: str) -> Call | None:
    call = db.query(Call).filter(Call.id == call_id).first()
    if call is None:
        return None
    call.summary = summary
    db.commit()
    db.refresh(call)
    return call


def list_calls(db: Session, page: int = 1, page_size: int = 20, verdict=None,
               scenario=None, date_from=None, date_to=None) -> dict:
    q = db.query(Call)
    if verdict:
        q = q.filter(Call.verdict == verdict)
    if scenario:
        q = q.filter(Call.scenario == scenario)
    if date_from:
        q = q.filter(Call.started_at >= date_from)
    if date_to:
        q = q.filter(Call.started_at <= date_to)
    total = q.count()
    rows = (q.order_by(Call.started_at.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    return {
        "items": [{
            "call_id": c.id, "source": c.source, "started_at": c.started_at,
            "duration_sec": c.duration_sec, "verdict": c.verdict,
            "scenario": c.scenario, "confidence": c.confidence,
        } for c in rows],
        "page": page, "page_size": page_size, "total": total,
        "pages": ceil(total / page_size) if total else 0,
    }


def get_call_detail(db: Session, call_id: str) -> dict | None:
    call = db.query(Call).filter(Call.id == call_id).first()
    if call is None:
        return None
    events = (db.query(CallEvent).filter(CallEvent.call_id == call_id)
              .order_by(CallEvent.at).all())
    return {
        "call": {
            "call_id": call.id, "source": call.source, "started_at": call.started_at,
            "ended_at": call.ended_at, "duration_sec": call.duration_sec,
            "verdict": call.verdict, "scenario": call.scenario,
            "confidence": call.confidence, "ended_reason": call.ended_reason,
            "job_id": call.job_id, "summary": call.summary, "audio_key": call.audio_key,
        },
        "events": [{"at": e.at, "speaker": e.speaker, "text": e.text,
                    "scam_delta": e.scam_delta} for e in events],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/call_agent/test_calls_crud.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add database/crud.py tests/call_agent/test_calls_crud.py
git commit -m "feat(call-agent): CRUD for calls and call events"
```

---

## Phase 4 — Orchestration

### Task 9: CallRecorder

**Files:**
- Create: `call_agent/recorder.py`
- Test: `tests/call_agent/test_recorder.py`

**Interfaces:**
- Consumes: `clients.minio_client.MinioStorageClient`, `crud.create_job`.
- Produces:
  - `class CallRecorder`:
    - `__init__(self, call_id, out_dir="/app/data/calls")` — opens a 16 kHz mono Int16 WAV at `{out_dir}/{call_id}.wav`.
    - `write_caller(self, pcm_bytes: bytes)` and `write_agent(self, pcm_bytes: bytes)` — append PCM (single mixed mono track: both sides written in the order they occur; acceptable for the prototype).
    - `close(self) -> str` — closes the WAV, returns local path.
    - `publish(self, minio, db, object_key=None) -> tuple[str, str]` — uploads WAV to MinIO under `calls/{call_id}.wav`, creates a `Job` via `crud.create_job(db, job_id=call_id, status="queued", audio_key=object_key, params={"source": "call_agent"})`, returns `(object_key, job_id)`. (Reuses call_id as job_id for a 1:1 link.)

- [ ] **Step 1: Write the failing test**

`tests/call_agent/test_recorder.py`:
```python
import os, wave
from call_agent.recorder import CallRecorder


def test_records_and_closes_wav(tmp_path):
    rec = CallRecorder("call-rec-1", out_dir=str(tmp_path))
    rec.write_caller(b"\x01\x00" * 1600)   # 0.1s
    rec.write_agent(b"\x02\x00" * 1600)
    path = rec.close()
    assert os.path.exists(path)
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnframes() == 3200


def test_publish_uploads_and_creates_job(tmp_path):
    rec = CallRecorder("call-rec-2", out_dir=str(tmp_path))
    rec.write_caller(b"\x00\x00" * 100)
    rec.close()

    uploaded = {}
    class FakeMinio:
        def upload_file(self, local_path, object_key, content_type=None):
            uploaded["key"] = object_key; return object_key
    created = {}
    class FakeDB: ...
    def fake_create_job(db, job_id, status, audio_key, params):
        created.update(job_id=job_id, audio_key=audio_key); return None

    import call_agent.recorder as rmod
    orig = rmod.crud.create_job
    rmod.crud.create_job = fake_create_job
    try:
        key, job_id = rec.publish(FakeMinio(), FakeDB())
    finally:
        rmod.crud.create_job = orig
    assert key == "calls/call-rec-2.wav"
    assert job_id == "call-rec-2"
    assert created["audio_key"] == "calls/call-rec-2.wav"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/call_agent/test_recorder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'call_agent.recorder'`

- [ ] **Step 3: Implement `call_agent/recorder.py`**

```python
"""Records both sides of a call to a WAV, then ships to MinIO + creates a Job."""
from __future__ import annotations

import os
import wave

from database import crud


class CallRecorder:
    def __init__(self, call_id: str, out_dir: str = "/app/data/calls"):
        self._call_id = call_id
        os.makedirs(out_dir, exist_ok=True)
        self._path = os.path.join(out_dir, f"{call_id}.wav")
        self._wav = wave.open(self._path, "wb")
        self._wav.setnchannels(1)
        self._wav.setsampwidth(2)
        self._wav.setframerate(16000)

    def write_caller(self, pcm_bytes: bytes) -> None:
        self._wav.writeframes(pcm_bytes)

    def write_agent(self, pcm_bytes: bytes) -> None:
        self._wav.writeframes(pcm_bytes)

    def close(self) -> str:
        self._wav.close()
        return self._path

    def publish(self, minio, db, object_key: str | None = None) -> tuple[str, str]:
        object_key = object_key or f"calls/{self._call_id}.wav"
        minio.upload_file(self._path, object_key, content_type="audio/wav")
        crud.create_job(db, job_id=self._call_id, status="queued",
                        audio_key=object_key, params={"source": "call_agent"})
        return object_key, self._call_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/call_agent/test_recorder.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add call_agent/recorder.py tests/call_agent/test_recorder.py
git commit -m "feat(call-agent): call recorder with MinIO upload + Job creation"
```

---

### Task 10: CallSession orchestrator

**Files:**
- Create: `call_agent/session.py`
- Test: `tests/call_agent/test_session.py`

**Interfaces:**
- Consumes: `ScamDetector`, `DialogEngine`, `StreamingASR`, `TTSService`, `CallRecorder`.
- Produces:
  - `class CallState(str, Enum)`: `GREETING`, `TALKING`, `HANGUP`, `TAKE_MESSAGE`, `ENDED`.
  - `class CallSession`:
    - `__init__(self, call_id, asr, detector, dialog, tts, recorder, on_event=None, now=time.monotonic)` — `on_event(at, speaker, text, scam_delta)` callback persists events; `now` injectable for deterministic tests.
    - `start(self) -> AgentAction` — returns the greeting action.
    - `on_pcm(self, pcm_bytes) -> list[AgentAction]` — feeds ASR + recorder; on a *final* utterance runs detector+dialog, may transition state; returns 0+ `AgentAction`s (a filler and/or a spoken reply and/or a hangup). On scam verdict → sets state `HANGUP`.
    - `tick(self) -> AgentAction | None` — called periodically; if `TALKING` and elapsed since start ≥ `not_scam_timeout_sec` (passed in) with no scam → transition `TAKE_MESSAGE`, return the take-message action.
    - `result(self) -> CallResult` — dataclass: `verdict`, `scenario`, `confidence`, `ended_reason`.
  - `AgentAction` dataclass: `type: str` (`"speak" | "hangup"`), `wav_path: str | None`, `text: str`.
  - Note: TTS is invoked inside the session to resolve a reply `text` → `wav_path` via `tts.synthesize(text)`.

- [ ] **Step 1: Write the failing test**

`tests/call_agent/test_session.py`:
```python
import os, json
import call_agent.config as cfg
from call_agent.scam_detector import load_scenarios, ScamDetector
from call_agent.dialog_engine import DialogEngine, load_replies
from call_agent.streaming_asr import StreamingASR
from call_agent.session import CallSession, CallState

SC = os.path.join(os.path.dirname(__file__), "..", "..", "call_agent", "scenarios")
RP = os.path.join(os.path.dirname(__file__), "..", "..", "call_agent", "persona", "replies.yaml")


class FakeTTS:
    def synthesize(self, text): return f"/tmp/{abs(hash(text))}.wav"


class ScriptRec:
    def __init__(self, finals): self._finals = finals; self._i = 0
    def AcceptWaveform(self, data): return True
    def Result(self):
        t = self._finals[self._i]; self._i += 1; return json.dumps({"text": t})
    def PartialResult(self): return json.dumps({"partial": ""})
    def FinalResult(self): return json.dumps({"text": ""})


class NullRecorder:
    def write_caller(self, b): pass
    def write_agent(self, b): pass


def _session(finals):
    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec(finals))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    return CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder())


def test_greeting_first():
    s = _session([])
    action = s.start()
    assert action.type == "speak"
    assert action.wav_path is not None


def test_scam_flow_hangs_up():
    s = _session(["служба безопасности банка", "карта заблокирована"])
    s.start()
    s.on_pcm(b"\x00\x00")                      # utterance 1: +40
    actions = s.on_pcm(b"\x00\x00")            # utterance 2: +30 -> 70 scam
    assert any(a.type == "hangup" for a in actions)
    assert s.result().verdict == "scam"
    assert s.result().scenario == "fake_bank"


def test_clean_call_keeps_talking():
    s = _session(["привет как дела"])
    s.start()
    actions = s.on_pcm(b"\x00\x00")
    assert all(a.type != "hangup" for a in actions)
    assert s.result().verdict == "undetermined"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/call_agent/test_session.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'call_agent.session'`

- [ ] **Step 3: Implement `call_agent/session.py`**

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/call_agent/test_session.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add call_agent/session.py tests/call_agent/test_session.py
git commit -m "feat(call-agent): CallSession orchestrator + state machine"
```

---

### Task 11: Full offline suite green

**Files:** none (verification task)

- [ ] **Step 1: Run the whole call_agent suite**

Run: `python -m pytest tests/call_agent/ -v`
Expected: all PASS (scam_detector, dialog_engine, config, tts_service, streaming_asr, summary, calls_crud, recorder, session).

- [ ] **Step 2: Run the existing suite to confirm no regressions**

Run: `python -m pytest tests/ -q`
Expected: existing tests still pass (models.py change is additive; crud.py additions don't touch existing functions).

- [ ] **Step 3: Commit (only if any fixups were needed)**

```bash
git add -A && git commit -m "test(call-agent): full offline suite green, no regressions"
```

---

## Phase 5 — Service + Wiring

### Task 12: FastAPI WebSocket app

**Files:**
- Create: `call_agent/main.py`
- Test: manual (WebSocket + models needed) — documented smoke steps; no unit test (integration by nature).

**Interfaces:**
- Consumes: everything above via a per-connection wiring function.
- Produces: FastAPI `app` with:
  - `GET /health` → `{"status": "ok"}`.
  - `WebSocket /ws/call` protocol:
    - On connect: create `call_id=uuid4()`, `crud.create_call(...)`, build session, send JSON `{"type":"agent_text","text":<greeting>}` then binary greeting WAV bytes.
    - Client sends **binary** frames = raw 16 kHz mono Int16LE PCM chunks (~200 ms).
    - For each chunk: `session.on_pcm(chunk)`; for each `AgentAction`: if `speak` send `{"type":"agent_text","text":...}` + binary WAV bytes; if `hangup` send `{"type":"hangup"}` and break.
    - A background timer calls `session.tick(settings.not_scam_timeout_sec)`.
    - On disconnect/hangup: `recorder.close()`, `recorder.publish(minio, db)`, `crud.finalize_call(...)`, then `build_pipeline_chain(job_id=call_id, input_key=object_key).apply_async(task_id=call_id)`, then (best-effort) after pipeline the summary is filled by a separate poll — for the prototype, call `summarize_transcript` is deferred to Task 16's "regenerate summary" button, so hangup path only finalizes + triggers pipeline.
  - `startup`: build shared `ScamDetector` scenarios, `DialogEngine` replies, `TTSService` and `warm_cache([...greetings + fillers + take_message...])`, single shared `StreamingASR`? No — ASR is stateful per call, so build a fresh `KaldiRecognizer` per connection but share the loaded Vosk `Model`. Store the shared `Model` and Silero model on `app.state`.
  - CORS: allow `CORS_ORIGINS` (same env as api) for the browser simulator.

- [ ] **Step 1: Implement `call_agent/main.py`**

```python
"""FastAPI service: one WebSocket endpoint drives a live call."""
from __future__ import annotations

import os
import uuid
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from call_agent.config import get_settings
from call_agent.scam_detector import load_scenarios, ScamDetector
from call_agent.dialog_engine import load_replies, DialogEngine
from call_agent.streaming_asr import StreamingASR
from call_agent.tts_service import TTSService
from call_agent.recorder import CallRecorder
from call_agent.session import CallSession
from clients.minio_client import MinioStorageClient
from database.session import SessionLocal
from database import crud
from tasks.audio_tasks import build_pipeline_chain

settings = get_settings()
app = FastAPI(title="Call Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    app.state.replies = load_replies(settings.replies_path)
    app.state.scenarios = load_scenarios(settings.scenarios_dir)
    app.state.tts = TTSService(settings)
    # Pre-synthesize every canned phrase so calls have zero TTS latency.
    canned = (app.state.replies["greeting"] + app.state.replies["fillers"]
              + app.state.replies["keep_talking"] + app.state.replies["take_message"])
    app.state.tts.warm_cache(canned)
    from vosk import Model
    app.state.vosk_model = Model(settings.vosk_model_path)


def _new_recognizer():
    from vosk import KaldiRecognizer
    rec = KaldiRecognizer(app.state.vosk_model, 16000)
    rec.SetWords(True)
    return rec


@app.get("/health")
def health():
    return {"status": "ok"}


def _read_wav_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


@app.websocket("/ws/call")
async def ws_call(ws: WebSocket):
    await ws.accept()
    call_id = str(uuid.uuid4())
    db = SessionLocal()
    recorder = CallRecorder(call_id)
    events: list[tuple] = []

    def on_event(at, speaker, text, delta):
        events.append((at, speaker, text, delta))

    crud.create_call(db, call_id, source="browser", started_at=datetime.utcnow())
    asr = StreamingASR(settings, recognizer=_new_recognizer())
    detector = ScamDetector(app.state.scenarios)
    dialog = DialogEngine(app.state.replies)
    session = CallSession(call_id, asr, detector, dialog, app.state.tts, recorder,
                          on_event=on_event)

    async def send_action(action):
        if action.type == "speak":
            await ws.send_json({"type": "agent_text", "text": action.text})
            wav = _read_wav_bytes(action.wav_path)
            recorder.write_agent(_pcm_from_wav(wav))
            await ws.send_bytes(wav)
        elif action.type == "hangup":
            await ws.send_json({"type": "hangup"})

    await send_action(session.start())

    ended_reason = "caller_hung_up"
    try:
        while True:
            chunk = await ws.receive_bytes()
            actions = session.on_pcm(chunk)
            for a in actions:
                await send_action(a)
                if a.type == "hangup":
                    ended_reason = "detected_scam"
                    raise WebSocketDisconnect()
            tick = session.tick(settings.not_scam_timeout_sec)
            if tick is not None:
                await send_action(tick)
    except WebSocketDisconnect:
        pass
    finally:
        _finalize(db, recorder, session, call_id, events, ended_reason)
        db.close()


def _pcm_from_wav(wav_bytes: bytes) -> bytes:
    # Strip 44-byte WAV header to get raw PCM for the mixed recording track.
    return wav_bytes[44:]


def _finalize(db, recorder, session, call_id, events, ended_reason):
    result = session.result()
    if result.verdict == "scam":
        ended_reason = "detected_scam"
    local = recorder.close()
    duration_sec = _wav_duration(local)
    minio = MinioStorageClient()
    object_key, job_id = recorder.publish(minio, db)
    for at, speaker, text, delta in events:
        crud.add_call_event(db, call_id, at, speaker, text, delta)
    crud.finalize_call(db, call_id, ended_at=datetime.utcnow(), duration_sec=duration_sec,
                       verdict=result.verdict, scenario=result.scenario,
                       confidence=result.confidence, ended_reason=result.ended_reason or ended_reason,
                       job_id=job_id, audio_key=object_key)
    build_pipeline_chain(job_id=job_id, input_key=object_key).apply_async(task_id=job_id)


def _wav_duration(path: str) -> float:
    import wave
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())
```

- [ ] **Step 2: Local import smoke check**

Run: `python -c "import call_agent.main"`
Expected: no import error (Vosk/Silero not loaded at import time — only inside startup/lazy). If `vosk`/`torch` not installed locally, this step is done inside the container in Task 13; note that and proceed.

- [ ] **Step 3: Commit**

```bash
git add call_agent/main.py
git commit -m "feat(call-agent): FastAPI WebSocket service driving live calls"
```

---

### Task 13: Dockerfile + compose wiring (call-agent + ollama)

**Files:**
- Create: `call_agent/Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `requirements.txt` (add `vosk`, `torch`, `pyyaml`, `httpx` if missing)

**Interfaces:** produces two new services: `call-agent` (port 8100) and `ollama` (port 11434).

- [ ] **Step 1: Add deps to `requirements.txt`**

Append if not present:
```
vosk==0.3.45
pyyaml
```
(`torch` and `httpx` are already used by the project via Silero/existing deps — verify with `grep -iE "torch|httpx" requirements.txt`; add `torch` only if absent, matching the version the existing image already installs.)

- [ ] **Step 2: Create `call_agent/Dockerfile`**

```dockerfile
FROM asr-app
# Reuse the base image (already has torch, numpy, sqlalchemy, minio, celery).
# Vosk + pyyaml are added via requirements.txt rebuild of asr-app, so no extra pip here.
WORKDIR /app
EXPOSE 8100
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["uvicorn call_agent.main:app --host 0.0.0.0 --port 8100"]
```

- [ ] **Step 3: Add services to `docker-compose.yml`**

Add under `services:` (models mounted via existing `models_cache` volume; place `vosk/` and `silero/` model files there once):
```yaml
  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - asr-net

  call-agent:
    build:
      context: .
      dockerfile: call_agent/Dockerfile
    image: asr-app
    restart: unless-stopped
    env_file:
      - .env
    environment:
      MODEL_CACHE_DIR: /app/models
      HF_HUB_OFFLINE: "1"
      OLLAMA_URL: "http://ollama:11434"
      CORS_ORIGINS: "http://localhost:5173,http://localhost:4000"
    volumes:
      - ./data:/app/data
      - models_cache:/app/models
    ports:
      - "${CALL_AGENT_PORT:-8100}:8100"
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - asr-net
```
And add `ollama_data:` to the `volumes:` block at the bottom.

- [ ] **Step 4: Build the base image (so vosk/pyyaml land in asr-app), then call-agent**

Run:
```bash
docker compose build api        # rebuilds asr-app with vosk + pyyaml
docker compose build call-agent
docker compose --env-file .env up -d ollama call-agent
docker compose exec ollama ollama pull qwen2.5:3b
```
Expected: `call-agent` healthy; `curl http://localhost:8100/health` → `{"status":"ok"}`.
NOTE: place `vosk-model-small-ru-0.22/` under the `models_cache` volume at `/app/models/vosk/` and `v4_ru.pt` at `/app/models/silero/` before first call (document in a follow-up README step). Vosk small-ru download: https://alphacephei.com/vosk/models ; Silero v4_ru: https://models.silero.ai/models/tts/ru/v4_ru.pt

- [ ] **Step 5: Commit**

```bash
git add call_agent/Dockerfile docker-compose.yml requirements.txt
git commit -m "feat(call-agent): Dockerfile + compose services (call-agent, ollama)"
```

---

## Phase 6 — Admin API + Frontend

### Task 14: Admin Calls routes

**Files:**
- Create: `api/routes/admin_calls.py`
- Modify: `api/routes/admin_router.py` (include the new router)
- Test: `tests/call_agent/test_admin_calls.py`

**Interfaces:**
- Consumes: `crud.list_calls`, `crud.get_call_detail`, `crud.set_call_summary`, `summarize_transcript`.
- Produces routes under `/v1/admin/calls`:
  - `GET ""` → paginated list; query params `page, page_size, verdict, scenario, date_from, date_to`; `Depends(get_current_user)`.
  - `GET "/{call_id}"` → detail dict; 404 if missing.
  - `POST "/{call_id}/summary"` → regenerate summary: loads the linked transcript full_text via existing transcript read, calls `summarize_transcript`, `crud.set_call_summary`, returns `{summary}`. (Uses existing `crud.get_transcript_for_job`-style reader — check the actual function name in crud for reading transcript text by job_id; if named differently, use that.)

- [ ] **Step 1: Write failing tests (mirror `tests/test_admin_audio.py` pattern)**

`tests/call_agent/test_admin_calls.py`:
```python
from datetime import datetime
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.auth_users import get_current_user
from api.main import app
from database.models import AdminUser

client = TestClient(app)

def _user(role="moderator"):
    u = AdminUser(); u.id = 1; u.login = "m"; u.role = role
    u.is_blocked = False; u.created_at = datetime(2026, 7, 1); return u

def _page(items):
    return {"items": items, "page": 1, "page_size": 20, "total": len(items), "pages": 1}

def test_list_calls_requires_auth():
    assert client.get("/v1/admin/calls").status_code == 401

def test_list_calls_returns_page():
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_calls.crud.list_calls", return_value=_page([])):
        r = client.get("/v1/admin/calls")
    app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 200
    assert r.json()["total"] == 0

def test_list_calls_passes_verdict_filter():
    captured = {}
    def fake(db, **kw): captured.update(kw); return _page([])
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_calls.crud.list_calls", side_effect=fake):
        r = client.get("/v1/admin/calls?verdict=scam")
    app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 200
    assert captured.get("verdict") == "scam"

def test_get_call_detail_404():
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_calls.crud.get_call_detail", return_value=None):
        r = client.get("/v1/admin/calls/nope")
    app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/call_agent/test_admin_calls.py -v`
Expected: FAIL (404 route not found → assertions fail / ImportError on router include)

- [ ] **Step 3: Implement `api/routes/admin_calls.py`**

```python
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import get_db
from api.auth_users import get_current_user
from database import crud

router = APIRouter(prefix="/calls", tags=["Admin Calls"])


@router.get("")
def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    verdict: Optional[str] = Query(None),
    scenario: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return crud.list_calls(db, page=page, page_size=page_size, verdict=verdict,
                           scenario=scenario, date_from=date_from, date_to=date_to)


@router.get("/{call_id}")
def get_call(call_id: str, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    detail = crud.get_call_detail(db, call_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Звонок не найден")
    return detail
```

- [ ] **Step 4: Wire the router in `api/routes/admin_router.py`**

Add import and include:
```python
from api.routes.admin_calls import router as admin_calls_router
# ...
admin_router.include_router(admin_calls_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/call_agent/test_admin_calls.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add api/routes/admin_calls.py api/routes/admin_router.py tests/call_agent/test_admin_calls.py
git commit -m "feat(call-agent): admin Calls list/detail routes"
```

---

### Task 15: Regenerate-summary route

**Files:**
- Modify: `api/routes/admin_calls.py` (add POST summary)
- Test: `tests/call_agent/test_admin_calls.py` (extend)

**Interfaces:**
- Consumes: `call_agent.summary.summarize_transcript`. Transcript full text is read
  directly from the `Transcript` table by `job_id` (the `Transcript` model has a
  `full_text` column — confirmed in `database/models.py:78`). We query it directly
  rather than reuse `crud.get_transcript_by_job_id` (which returns a segment dict,
  not a plain string), keeping the summary path simple.

- [ ] **Step 1: Write the failing test (extend file)**

```python
def test_regenerate_summary_sets_and_returns():
    app.dependency_overrides[get_current_user] = lambda: _user("super_admin")
    detail = {"call": {"job_id": "job-1"}, "events": []}
    with patch("api.routes.admin_calls.crud.get_call_detail", return_value=detail), \
         patch("api.routes.admin_calls._transcript_text", return_value="расшифровка"), \
         patch("api.routes.admin_calls.summarize_transcript", return_value="Кратко: банк."), \
         patch("api.routes.admin_calls.crud.set_call_summary", return_value=None) as setter:
        r = client.post("/v1/admin/calls/call-1/summary")
    app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 200
    assert r.json()["summary"] == "Кратко: банк."
    setter.assert_called_once()
```

Note: `_transcript_text` is patched here, so the test does not touch the DB.
The real implementation queries `Transcript.full_text` directly (Step 3).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/call_agent/test_admin_calls.py::test_regenerate_summary_sets_and_returns -v`
Expected: FAIL (route missing)

- [ ] **Step 3: Add the route to `api/routes/admin_calls.py`**

```python
from call_agent.summary import summarize_transcript
from call_agent.config import get_settings
from database.models import Transcript


def _transcript_text(db, job_id: str) -> str | None:
    row = db.query(Transcript).filter(Transcript.job_id == job_id).first()
    return row.full_text if row else None


@router.post("/{call_id}/summary")
def regenerate_summary(call_id: str, db: Session = Depends(get_db),
                       _user=Depends(get_current_user)):
    detail = crud.get_call_detail(db, call_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Звонок не найден")
    job_id = detail["call"].get("job_id")
    text = _transcript_text(db, job_id) if job_id else None
    if not text:
        raise HTTPException(status_code=409, detail="Транскрипция ещё не готова")
    summary = summarize_transcript(text, get_settings())
    if summary is None:
        raise HTTPException(status_code=502, detail="Сервис выжимки недоступен")
    crud.set_call_summary(db, call_id, summary)
    return {"summary": summary}
```
(At implementation time, replace `crud.get_transcript_by_job` and `.get("full_text")` with the real reader discovered in `crud.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/call_agent/test_admin_calls.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add api/routes/admin_calls.py tests/call_agent/test_admin_calls.py
git commit -m "feat(call-agent): regenerate call summary via Ollama"
```

---

### Task 16: Calls list page (frontend)

**Files:**
- Create: `frontend/src/pages/CallsListPage.tsx`
- Modify: `frontend/src/components/Nav.tsx` (add "Звонки")
- Modify: `frontend/src/App.tsx` (add route)

**Interfaces:** consumes `GET /v1/admin/calls`. Mirrors `AudioListPage.tsx` structure (filters + table + pagination).

- [ ] **Step 1: Create `CallsListPage.tsx`**

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface CallItem {
  call_id: string; source: string; started_at: string;
  duration_sec: number | null; verdict: string;
  scenario: string | null; confidence: number;
}
interface CallsResponse { items: CallItem[]; page: number; pages: number; total: number; }

const VERDICT = { scam: "🔴 Мошенник", not_scam: "🟢 Чисто", undetermined: "⚪ Не определён" } as Record<string,string>;

export function CallsListPage() {
  const { token } = useAuth();
  const [verdict, setVerdict] = useState("");
  const [data, setData] = useState<CallsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function load(page = 1) {
    setLoading(true);
    const p = new URLSearchParams({ page: String(page), page_size: "20" });
    if (verdict) p.set("verdict", verdict);
    const r = await fetch(`${API_BASE}/v1/admin/calls?${p}`, { headers: { Authorization: `Bearer ${token}` } });
    setData(await r.json());
    setLoading(false);
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Звонки</h1>
      <div className="bg-white rounded-lg shadow p-4 mb-6 flex gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Вердикт</label>
          <select value={verdict} onChange={e => setVerdict(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2 text-sm">
            <option value="">Все</option>
            <option value="scam">Мошенник</option>
            <option value="not_scam">Чисто</option>
            <option value="undetermined">Не определён</option>
          </select>
        </div>
        <button onClick={() => load(1)} disabled={loading}
          className="bg-blue-600 text-white px-5 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50">
          {loading ? "Загрузка…" : "Показать"}
        </button>
      </div>
      {data && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3">Дата</th>
                <th className="text-left px-4 py-3">Источник</th>
                <th className="text-left px-4 py-3">Длит.</th>
                <th className="text-left px-4 py-3">Вердикт</th>
                <th className="text-left px-4 py-3">Сценарий</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.items.map(c => (
                <tr key={c.call_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link to={`/calls/${c.call_id}`} className="text-blue-600 hover:underline">
                      {new Date(c.started_at).toLocaleString("ru-RU")}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{c.source}</td>
                  <td className="px-4 py-3">{c.duration_sec ? `${Math.round(c.duration_sec)} с` : "—"}</td>
                  <td className="px-4 py-3">{VERDICT[c.verdict] ?? c.verdict}</td>
                  <td className="px-4 py-3">{c.scenario ?? "—"}</td>
                </tr>
              ))}
              {data.items.length === 0 && (
                <tr><td colSpan={5} className="text-center py-8 text-gray-400">Звонков нет</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add nav item in `Nav.tsx`**

Add to `NAV_ITEMS` after the audio item:
```tsx
{ path: "/calls", label: "Звонки", roles: ["moderator", "super_admin"] },
```

- [ ] **Step 3: Add routes in `App.tsx`**

Add import and routes (detail page created in Task 17, simulator in Task 18):
```tsx
import { CallsListPage } from "./pages/CallsListPage";
// inside <Routes>:
<Route path="/calls" element={<CallsListPage />} />
```

- [ ] **Step 4: Build the frontend**

Run: `docker compose build frontend && docker compose --env-file .env up -d frontend`
Expected: build succeeds; `/calls` shows the list page.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CallsListPage.tsx frontend/src/components/Nav.tsx frontend/src/App.tsx
git commit -m "feat(call-agent): Calls list page + nav"
```

---

### Task 17: Call detail page (frontend)

**Files:**
- Create: `frontend/src/pages/CallDetailPage.tsx`
- Modify: `frontend/src/App.tsx` (add `/calls/:callId` route)

**Interfaces:** consumes `GET /v1/admin/calls/{id}` and `POST /v1/admin/calls/{id}/summary`.

**Spec note — full transcript + audio player:** The spec asks the detail view to
expose the call recording player and the full pipeline transcript with audit
logging. Because `call_id == job_id`, the recording and its Whisper transcript are
a normal `Job`, already viewable at the existing `/audio/{job_id}` page — which
already has the audio player AND writes the audit-log entry on transcript reveal
(Constitution Principle VI). So this page does NOT re-implement the player or
transcript; it links to `/audio/{job_id}` for the audited full view. This reuse is
intentional and avoids duplicating the audit path.

- [ ] **Step 1: Create `CallDetailPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

interface Ev { at: number; speaker: string; text: string; scam_delta: number; }
interface Detail {
  call: { call_id: string; verdict: string; scenario: string | null; confidence: number;
    ended_reason: string | null; summary: string | null; duration_sec: number | null;
    job_id: string | null; };
  events: Ev[];
}

export function CallDetailPage() {
  const { callId } = useParams();
  const { token } = useAuth();
  const [d, setD] = useState<Detail | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const r = await fetch(`${API_BASE}/v1/admin/calls/${callId}`, { headers: { Authorization: `Bearer ${token}` } });
    if (r.ok) setD(await r.json());
  }
  useEffect(() => { load(); }, [callId]);

  async function regen() {
    setBusy(true);
    await fetch(`${API_BASE}/v1/admin/calls/${callId}/summary`, {
      method: "POST", headers: { Authorization: `Bearer ${token}` },
    });
    await load(); setBusy(false);
  }

  if (!d) return <div className="p-6 text-gray-400">Загрузка…</div>;
  const c = d.call;
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Звонок</h1>
      <div className="bg-white rounded-lg shadow p-4 mb-4">
        <div className="text-lg font-medium mb-2">
          {c.verdict === "scam" ? "🔴 Мошенник" : c.verdict === "not_scam" ? "🟢 Чисто" : "⚪ Не определён"}
          {c.scenario && <span className="text-gray-500 text-sm ml-2">({c.scenario}, {c.confidence}%)</span>}
        </div>
        <div className="bg-gray-50 rounded p-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs font-medium text-gray-500">Краткая выжимка</span>
            <button onClick={regen} disabled={busy}
              className="text-xs text-blue-600 hover:underline disabled:opacity-50">
              {busy ? "Генерация…" : "Обновить"}
            </button>
          </div>
          <p className="text-sm text-gray-800">{c.summary ?? "Выжимка ещё не готова."}</p>
        </div>
        {c.job_id && (
          <a href={`/audio/${c.job_id}`}
             className="inline-block mt-3 text-sm text-blue-600 hover:underline">
            Открыть запись и полную транскрипцию →
          </a>
        )}
      </div>
      <div className="bg-white rounded-lg shadow divide-y divide-gray-100">
        {d.events.map((e, i) => (
          <div key={i} className={`p-3 flex gap-3 ${e.scam_delta > 0 ? "bg-red-50" : ""}`}>
            <span className="text-xs text-gray-400 w-12">{e.at.toFixed(1)}с</span>
            <span className={`text-xs font-medium w-16 ${e.speaker === "agent" ? "text-blue-600" : "text-gray-700"}`}>
              {e.speaker === "agent" ? "Агент" : "Звонящий"}
            </span>
            <span className="text-sm flex-1">{e.text}</span>
            {e.scam_delta > 0 && <span className="text-xs text-red-500">+{e.scam_delta}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add route in `App.tsx`**

```tsx
import { CallDetailPage } from "./pages/CallDetailPage";
<Route path="/calls/:callId" element={<CallDetailPage />} />
```

- [ ] **Step 3: Build + verify**

Run: `docker compose build frontend && docker compose --env-file .env up -d frontend`
Expected: clicking a call opens the detail with verdict, summary, and highlighted scam events.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/CallDetailPage.tsx frontend/src/App.tsx
git commit -m "feat(call-agent): call detail page with summary + event timeline"
```

---

### Task 18: Browser call simulator page

**Files:**
- Create: `frontend/src/pages/CallSimulatorPage.tsx`
- Modify: `frontend/src/components/Nav.tsx` (add "Симулятор")
- Modify: `frontend/src/App.tsx` (add `/simulator` route)

**Interfaces:** opens a WebSocket to the call-agent (`ws://localhost:8100/ws/call` via env `VITE_CALL_AGENT_WS`), captures mic PCM at 16 kHz Int16, streams binary chunks, plays back agent WAV replies, shows live agent text and a hangup banner.

- [ ] **Step 1: Create `CallSimulatorPage.tsx`**

```tsx
import { useRef, useState } from "react";

const WS_URL = import.meta.env.VITE_CALL_AGENT_WS ?? "ws://localhost:8100/ws/call";

export function CallSimulatorPage() {
  const [active, setActive] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  function pushLog(line: string) { setLog(l => [...l, line]); }

  async function start() {
    setLog([]); setActive(true);
    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onmessage = async (ev) => {
      if (typeof ev.data === "string") {
        const msg = JSON.parse(ev.data);
        if (msg.type === "agent_text") pushLog(`Агент: ${msg.text}`);
        if (msg.type === "hangup") { pushLog("— Агент завершил звонок —"); stop(); }
      } else {
        const ctx = ctxRef.current!;
        const buf = await ctx.decodeAudioData(ev.data.slice(0));
        const src = ctx.createBufferSource();
        src.buffer = buf; src.connect(ctx.destination); src.start();
      }
    };

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    const ctx = new AudioContext({ sampleRate: 16000 });
    ctxRef.current = ctx;
    const source = ctx.createMediaStreamSource(stream);
    const proc = ctx.createScriptProcessor(4096, 1, 1);
    source.connect(proc); proc.connect(ctx.destination);
    proc.onaudioprocess = (e) => {
      if (ws.readyState !== WebSocket.OPEN) return;
      const f32 = e.inputBuffer.getChannelData(0);
      const i16 = new Int16Array(f32.length);
      for (let i = 0; i < f32.length; i++) {
        const s = Math.max(-1, Math.min(1, f32[i]));
        i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      ws.send(i16.buffer);
    };
  }

  function stop() {
    setActive(false);
    wsRef.current?.close();
    streamRef.current?.getTracks().forEach(t => t.stop());
    ctxRef.current?.close();
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Симулятор звонка</h1>
      <p className="text-sm text-gray-500 mb-4">
        Нажмите «Позвонить», говорите в микрофон как мошенник — агент ответит голосом.
      </p>
      {!active
        ? <button onClick={start} className="bg-green-600 text-white px-6 py-2.5 rounded-lg">Позвонить</button>
        : <button onClick={stop} className="bg-red-600 text-white px-6 py-2.5 rounded-lg">Завершить</button>}
      <div className="mt-4 bg-white rounded-lg shadow p-4 min-h-40 space-y-1">
        {log.map((l, i) => <div key={i} className="text-sm">{l}</div>)}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add nav item + route**

`Nav.tsx` (super_admin only, since it's a test tool):
```tsx
{ path: "/simulator", label: "Симулятор", roles: ["super_admin"] },
```
`App.tsx`:
```tsx
import { CallSimulatorPage } from "./pages/CallSimulatorPage";
<Route path="/simulator" element={<CallSimulatorPage />} />
```

- [ ] **Step 3: Add `VITE_CALL_AGENT_WS` to frontend build args**

In `docker-compose.yml` frontend `build.args`, add `VITE_CALL_AGENT_WS: "ws://localhost:8100/ws/call"` (dev override; in prod route via nginx wss).

- [ ] **Step 4: End-to-end manual test**

Run: `docker compose --env-file .env up -d call-agent ollama frontend`
Steps: open `/simulator`, click «Позвонить», say «Здравствуйте, это служба безопасности банка, ваша карта заблокирована, продиктуйте код из СМС». Expected: agent greets, plays fillers/keep-talking, then hangs up on scam; a new row appears in `/calls` with verdict «Мошенник», scenario `fake_bank`, and an event timeline. After the Whisper pipeline finishes, «Обновить» on the detail page fills the summary.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CallSimulatorPage.tsx frontend/src/components/Nav.tsx frontend/src/App.tsx docker-compose.yml
git commit -m "feat(call-agent): browser call simulator page (mic -> WebSocket)"
```

---

## Done When (Stage 1)

- [ ] `python -m pytest tests/call_agent/ -v` all green; existing `tests/` still green.
- [ ] `docker compose up -d call-agent ollama` healthy; `/health` returns ok.
- [ ] Browser simulator: a scripted "bank scam" call → agent greets, stalls with fillers, hangs up, and a scam-verdict call with event timeline appears in `/calls`.
- [ ] A non-scam call → after `NOT_SCAM_TIMEOUT_SEC` the agent offers to take a message.
- [ ] Call recording lands in MinIO, Whisper pipeline produces a transcript, and «Обновить выжимку» fills the Ollama summary on the detail page.
- [ ] No pipeline files modified; audit/auth reused unchanged.

## Deferred to Stage 2 (not in this plan)

- Telegram userbot transport (TDLib/tgcalls) replacing the browser WebSocket.
- Speaker-voice identification by embeddings.
- LLM-based scam classifier alongside the rules.
- Concurrent multi-call handling and per-call background tick scheduling hardening.
- Auto-summary on pipeline completion (currently manual «Обновить» button).
