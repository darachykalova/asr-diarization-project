# n8n Telegram Call-Alert Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After every call handled by `call-agent`, send a minimal `{call_id, verdict}` webhook to a local n8n workflow that relays a short Telegram message to a fixed chat.

**Architecture:** `call_agent/main.py:_finalize()` calls a small new helper `_send_call_alert()` right after `crud.finalize_call(...)`, which posts to `services.webhook_service.send_webhook()` if `N8N_CALL_ALERT_WEBHOOK_URL` is configured. n8n receives the POST on a Webhook trigger node and forwards it to a Telegram "Send Message" node whose text is built with an inline expression based on `verdict`.

**Tech Stack:** Python (FastAPI service `call_agent`), existing `services/webhook_service.py` (HMAC-signed POST with retries), n8n (already running locally per `docker-compose.yml`, service name `n8n`, port 5678).

## Global Constraints

- Notification fires for **any** call verdict (`scam` / `undetermined` / `took_message`), not only `scam`.
- Message payload is minimal: exactly `{"call_id": ..., "verdict": ...}` — no scenario, confidence, or duration.
- URL lives in a new optional env var `N8N_CALL_ALERT_WEBHOOK_URL` (no default — unset means the step is skipped entirely).
- Delivery reuses the existing `services.webhook_service.send_webhook()` helper (HMAC signature + retries) — do not add a second HTTP-call mechanism.
- The alert call happens only on the success path of `_finalize()`, never from the `_safe_finalize()` except-fallback.
- A webhook failure must never block or fail call finalization (best-effort, logged, swallowed).
- Telegram `chatId` is hardcoded to `1109993976` inside the n8n Telegram node (not a parameter from Python).
- The n8n workflow must be manually activated (Active toggle) after import so its **Production URL** works, not just the Test URL.

---

### Task 1: `N8N_CALL_ALERT_WEBHOOK_URL` config setting

**Files:**
- Modify: `call_agent/config.py:22` (after `self.tts_cache_dir = ...`)
- Test: `tests/call_agent/test_config.py`

**Interfaces:**
- Produces: `Settings.n8n_call_alert_webhook_url: str | None`, read via `call_agent.config.get_settings()`. Task 2 consumes this attribute.

- [ ] **Step 1: Write the failing tests**

Edit `tests/call_agent/test_config.py` — add `"N8N_CALL_ALERT_WEBHOOK_URL"` to the `delenv` loop in `test_defaults` and assert the new default, then add a new test for the env override:

```python
import importlib


def test_defaults(monkeypatch):
    for var in ["VOSK_MODEL_PATH", "SILERO_SPEAKER", "NOT_SCAM_TIMEOUT_SEC",
                "N8N_CALL_ALERT_WEBHOOK_URL"]:
        monkeypatch.delenv(var, raising=False)
    import call_agent.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.silero_speaker == "baya"
    assert s.not_scam_timeout_sec == 180
    assert s.scenarios_dir.endswith("scenarios")
    assert s.n8n_call_alert_webhook_url is None


def test_env_override(monkeypatch):
    monkeypatch.setenv("SILERO_SPEAKER", "xenia")
    monkeypatch.setenv("NOT_SCAM_TIMEOUT_SEC", "90")
    import call_agent.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.silero_speaker == "xenia"
    assert s.not_scam_timeout_sec == 90


def test_call_alert_webhook_env_override(monkeypatch):
    monkeypatch.setenv("N8N_CALL_ALERT_WEBHOOK_URL", "http://n8n:5678/webhook/call-alert")
    import call_agent.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.n8n_call_alert_webhook_url == "http://n8n:5678/webhook/call-alert"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/call_agent/test_config.py -v`
Expected: `test_defaults` and `test_call_alert_webhook_env_override` FAIL with `AttributeError: 'Settings' object has no attribute 'n8n_call_alert_webhook_url'`

- [ ] **Step 3: Add the setting**

In `call_agent/config.py`, inside `Settings.__init__`, right after the existing `self.tts_cache_dir = ...` line, add:

```python
        self.n8n_call_alert_webhook_url = os.getenv("N8N_CALL_ALERT_WEBHOOK_URL")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/call_agent/test_config.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add call_agent/config.py tests/call_agent/test_config.py
git commit -m "feat(call-agent): add N8N_CALL_ALERT_WEBHOOK_URL setting"
```

---

### Task 2: `_send_call_alert` helper wired into `_finalize`

**Files:**
- Modify: `call_agent/main.py:168-198` (add helper before `_finalize`, call it inside `_finalize`)
- Test: Create `tests/call_agent/test_main_alert.py`

**Interfaces:**
- Consumes: `call_agent.config.Settings.n8n_call_alert_webhook_url` (Task 1). `services.webhook_service.send_webhook(url: str, payload: dict, max_retries: int = 3) -> bool` (existing, unchanged).
- Produces: `call_agent.main._send_call_alert(webhook_url: str | None, call_id: str, verdict: str) -> None`. Called from `_finalize()`; no other task depends on it.

- [ ] **Step 1: Write the failing tests**

Create `tests/call_agent/test_main_alert.py`:

```python
from unittest.mock import patch

from call_agent.main import _send_call_alert


def test_send_call_alert_posts_to_webhook_when_configured():
    with patch("services.webhook_service.send_webhook") as mock_send:
        _send_call_alert("http://n8n:5678/webhook/call-alert", "call-123", "scam")
    mock_send.assert_called_once_with(
        url="http://n8n:5678/webhook/call-alert",
        payload={"call_id": "call-123", "verdict": "scam"},
    )


def test_send_call_alert_skips_when_url_not_configured():
    with patch("services.webhook_service.send_webhook") as mock_send:
        _send_call_alert(None, "call-123", "scam")
    mock_send.assert_not_called()


def test_send_call_alert_swallows_webhook_errors():
    with patch("services.webhook_service.send_webhook", side_effect=RuntimeError("boom")):
        _send_call_alert("http://n8n:5678/webhook/call-alert", "call-123", "undetermined")
        # must not raise — the assertion is simply that this line is reached
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/call_agent/test_main_alert.py -v`
Expected: FAIL with `ImportError: cannot import name '_send_call_alert' from 'call_agent.main'`

- [ ] **Step 3: Add the helper and wire it into `_finalize`**

In `call_agent/main.py`, add this function right after `_pcm_from_wav` (before `def _finalize`):

```python
def _send_call_alert(webhook_url: str | None, call_id: str, verdict: str) -> None:
    if not webhook_url:
        return
    try:
        from services.webhook_service import send_webhook
        send_webhook(url=webhook_url, payload={"call_id": call_id, "verdict": verdict})
    except Exception as exc:
        logger.warning("Call %s: n8n alert webhook failed: %s", call_id, exc)
```

Then in `_finalize()`, insert the call right after `crud.finalize_call(...)` and its trailing comment, before the `build_pipeline_chain(...)` dispatch line:

```python
    crud.finalize_call(db, call_id, ended_at=datetime.utcnow(), duration_sec=duration_sec,
                       verdict=result.verdict, scenario=result.scenario,
                       confidence=result.confidence, ended_reason=result.ended_reason or ended_reason,
                       job_id=job_id, audio_key=object_key)
    # finalize_call already calls db.commit(), which commits events + call row together
    _send_call_alert(settings.n8n_call_alert_webhook_url, call_id, result.verdict)
    build_pipeline_chain(job_id=job_id, input_key=object_key).apply_async(task_id=job_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/call_agent/test_main_alert.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full call-agent test suite to check nothing broke**

Run: `python -m pytest tests/call_agent/ -v`
Expected: PASS (all tests, including the new ones)

- [ ] **Step 6: Commit**

```bash
git add call_agent/main.py tests/call_agent/test_main_alert.py
git commit -m "feat(call-agent): send n8n alert webhook on call finalize"
```

---

### Task 3: n8n workflow file, docs, and end-to-end verification

**Files:**
- Create: `n8n/workflows/call-alert-telegram.json`
- Modify: `CLAUDE.md` (call-agent architecture paragraph — document the new env var)

**Interfaces:**
- Consumes: nothing from earlier tasks directly — this is the receiving side. Relies on Task 2's POST body shape `{"call_id": ..., "verdict": ...}`.
- Produces: nothing consumed by other tasks — this is the last task.

- [ ] **Step 1: Create the workflow directory and file**

```bash
mkdir -p n8n/workflows
```

Write `n8n/workflows/call-alert-telegram.json`:

```json
{
  "name": "Call Alert -> Telegram",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "call-alert",
        "options": {}
      },
      "id": "c9c1a2e4-6f3b-4a1d-9e2a-1a2b3c4d5e6f",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2,
      "position": [260, 300],
      "webhookId": "b1e6d5c4-3f2e-4a1b-9c8d-7e6f5a4b3c2d"
    },
    {
      "parameters": {
        "chatId": "1109993976",
        "text": "={{ $json.body.verdict === 'scam' ? '⚠️ Мошенник обнаружен' : 'Звонок завершён: ' + $json.body.verdict }} (call_id: {{ $json.body.call_id }})",
        "additionalFields": {}
      },
      "id": "a3b2c1d0-5e4f-4c3b-8a19-2b3c4d5e6f70",
      "name": "Telegram",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1.2,
      "position": [520, 300],
      "credentials": {
        "telegramApi": {
          "id": "",
          "name": "Telegram account"
        }
      }
    }
  ],
  "connections": {
    "Webhook": {
      "main": [
        [
          {
            "node": "Telegram",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  },
  "active": false,
  "settings": {
    "executionOrder": "v1"
  }
}
```

- [ ] **Step 2: Import and configure the workflow in n8n**

Open http://localhost:5678 → menu → *Import from File* → select `n8n/workflows/call-alert-telegram.json`.

Open the **Telegram** node → *Credential* dropdown → *Create New* → paste the existing bot token (from @BotFather, the same one used in the earlier cloud-n8n setup) → save as "Telegram account".

Toggle the workflow **Active** (top-right switch). Open the **Webhook** node and copy the *Production URL* shown there — it should be `http://localhost:5678/webhook/call-alert` from the host, and `http://n8n:5678/webhook/call-alert` from inside the docker network (this is the value call-agent needs).

- [ ] **Step 3: Document the env var in CLAUDE.md**

In `CLAUDE.md`, find the call-agent architecture bullet (the paragraph starting `**Call-agent (анти-скам голосовой агент)**`) and append this sentence at the end of it, before the closing paragraph break:

```
 Опционально `N8N_CALL_ALERT_WEBHOOK_URL` — если задан, после каждого звонка `_finalize` в `call_agent/main.py` шлёт best-effort webhook `{call_id, verdict}` на этот URL (обычно локальный n8n: `http://n8n:5678/webhook/call-alert`); сам workflow — `n8n/workflows/call-alert-telegram.json`, импортировать и активировать вручную через n8n UI (http://localhost:5678).
```

- [ ] **Step 4: Set the env var and rebuild call-agent**

Add to your local `.env` (not committed — gitignored):

```
N8N_CALL_ALERT_WEBHOOK_URL=http://n8n:5678/webhook/call-alert
```

Rebuild and restart (call-agent's image is built `FROM asr-app`, so rebuild `api` first per `CLAUDE.md`):

```bash
docker compose build api && docker compose build call-agent && docker compose up -d call-agent
```

- [ ] **Step 5: Manual end-to-end verification**

Open the call-agent browser simulator, run a short test call through to completion (any verdict is fine — a plain non-scam conversation is enough since the alert fires for every verdict).

Confirm a message arrives in the Telegram chat, either:
- `⚠️ Мошенник обнаружен (call_id: <uuid>)` if the scenario triggered a scam verdict, or
- `Звонок завершён: <verdict> (call_id: <uuid>)` otherwise.

If nothing arrives, check `docker compose logs call-agent --tail 50` for the `n8n alert webhook failed` warning, and `docker compose logs n8n --tail 50` for webhook receipt/execution errors.

- [ ] **Step 6: Commit**

```bash
git add n8n/workflows/call-alert-telegram.json CLAUDE.md
git commit -m "feat(call-agent): n8n workflow + docs for Telegram call alerts"
```

---

## Self-Review Notes

- **Spec coverage:** trigger (any verdict) → Task 2; minimal payload → Task 2 test; env var config → Task 1; reuse of `webhook_service.send_webhook` → Task 2; success-path-only call site → Task 2 Step 3; best-effort/non-blocking → Task 2 helper + tests; n8n workflow shape (Webhook → Telegram, expression-based text, hardcoded chatId, manual activation) → Task 3; testing (unit test on the alert-sending behavior + manual verification) → Task 1/2 unit tests + Task 3 Step 5. All spec sections have a task.
- **Placeholder scan:** no TBD/TODO; every step has literal code, commands, or exact UI actions.
- **Type consistency:** `Settings.n8n_call_alert_webhook_url` (Task 1) matches the attribute name read in `_finalize()` (Task 2). `_send_call_alert(webhook_url, call_id, verdict)` signature matches every call site and every test invocation.
