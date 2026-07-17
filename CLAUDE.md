# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Design Context

For `frontend/` UI/UX work, `PRODUCT.md` and `DESIGN.md` at the repo root capture the admin console's product register, users, brand personality, and visual system (colors, typography, components) — written 2026-07-16 via the `impeccable` skill. Read them before making design decisions; every `impeccable` command reads them automatically.

## Commands

```bash
# Rebuild after code changes (COPY bakes code into image — restart alone is not enough)
docker compose build api worker && docker compose up -d api worker

# call-agent builds FROM asr-app: rebuild api (asr-app) first, then call-agent
docker compose build api && docker compose build call-agent && docker compose up -d call-agent

# Tests — what CI actually runs (no containers, ML stack mocked in tests/conftest.py)
python -m pytest tests/ -m "not requires_torch and not requires_db"
python -m pytest tests/test_api.py::test_health_check   # single test

# Tests needing real Postgres (marked requires_db, e.g. test_crud_search.py, test_job_recovery.py)
# require `docker compose up -d postgres` first and DATABASE_URL pointing at it
python -m pytest tests/ -m requires_db

# Lint
ruff check .

# First-time setup
docker compose build --build-arg HF_TOKEN=hf_xxx
docker compose exec api python scripts/create_api_key.py
docker compose exec worker python scripts/verify_models.py
docker compose exec call-agent python scripts/verify_call_agent_models.py
docker compose exec ollama ollama pull qwen2.5:3b   # модель семантической проверки мошенничества (иначе проверка всегда отвечает «не мошенник», см. warning в логах call-agent)

# Admin console — первый запуск
docker compose exec api python scripts/bootstrap_admin.py --login admin --role super_admin
# (пароль берётся из --password или env ADMIN_BOOTSTRAP_PASSWORD или интерактивно)

# Frontend (dev)
cd frontend && npm install && npm run dev   # http://localhost:5173

# Frontend (prod build) — раздаётся nginx-контейнером на порту ${FRONTEND_PORT:-5173}
docker compose build frontend && docker compose up -d frontend

# MCP-сервер (поиск по транскриптам + статистика звонков из Claude Code)
pip install -r mcp_server/requirements.txt   # один раз, на хосте
# дальше ничего запускать не надо: Claude Code сам поднимает сервер по .mcp.json
```

## Architecture

**One image (`asr-app`), two roles:** `api` (FastAPI + Uvicorn) queues jobs; `worker` (Celery prefork, concurrency=2) runs them.

**Pipeline chain** — assembled in `tasks/audio_tasks.py:build_pipeline_chain()`, executed in `tasks/pipeline_tasks.py`. Each task passes a `ctx` dict to the next. Context keys per task are documented at the top of `pipeline_tasks.py`.

```
normalize → asr → diarize → merge_align → persist → identify_speakers → finalize
```

**Chunking + auto model selection** — `asr_task` calls `chunking_service.split_audio()` for audio >6 min. Splits at VAD silence boundaries (pyannote `_segmentation`, already cached) with energy fallback. Each chunk gets its own SNR → Whisper model (tiny/base/large-v2). Diarization always runs on the full file.

**Model cache** — `services/model_cache.py` stores all ML models in module-level globals per worker process (load once, reuse across jobs). Startup refuses if any of the 5 required models are missing locally (`services/model_registry.py`). Models live in MinIO bucket `ml-models`; on startup each worker runs `scripts/sync_models_from_minio.py` (skips if already present locally) so a new worker/machine doesn't need the image rebuilt with `HF_TOKEN` to get models.

**Reliability** — pipeline tasks auto-retry transient failures (exponential backoff + jitter); after retries are exhausted the job routes to the `dead_letter` queue and is marked `failed` with `error_code=MAX_RETRIES_EXCEEDED`. `task_acks_late=True` + `task_reject_on_worker_lost=True` mean a job killed mid-flight (e.g. OOM) is requeued, not lost — separate from the worker-restart self-healing below.

**Worker self-healing** — `tasks/recovery.py:requeue_stuck_jobs()` runs once per worker start (`worker_ready` signal in `tasks/audio_tasks.py`, not per prefork child). It finds jobs stuck in `processing`/`queued` past `STUCK_JOB_MAX_AGE_HOURS` (default 2h) — orphaned when a worker or Redis died mid-job, since `task_acks_late` doesn't help if the broker itself is lost — and re-submits the pipeline chain for them (safe because `persist_task` deletes the old transcript before writing, so re-running is idempotent). Jobs with no `audio_key` can't be requeued and are marked `failed` instead.

**DB layer** — all ops in `database/crud.py`. Celery task functions take `db: Session` (caller manages). Transcript query functions (used by API routes) manage `SessionLocal()` internally. `database/repository.py` was deleted.

**Auth** — `api/auth.py`, Bearer token with scope `read`/`write`/`admin`. Test override: `app.dependency_overrides[verify_api_key] = lambda: mock_key`.

**Admin console** — веб-интерфейс в `frontend/` (React+Vite). Отдельный JWT-слой в `api/auth_users.py` (не пересекается с API-key auth). Маршруты под `/v1/admin/*` подключены через `api/routes/admin_router.py`. Роли: `moderator` (аудио+транскрипции), `super_admin` (+ пользователи, аудит, настройки). Тест-оверрайд: `app.dependency_overrides[get_current_user] = lambda: mock_admin`.

**Call-agent (анти-скам голосовой агент)** — отдельный сервис `call_agent/` на своём образе `asr-call-agent` (FROM asr-app), порт 8100. Один WebSocket endpoint `/ws/call` (`call_agent/main.py`) ведёт звонок: браузер шлёт PCM16@16kHz чанки, агент отвечает JSON (`agent_text`/`hangup`) + WAV-байтами. Внутри: `streaming_asr.py` (Vosk), `scam_detector.py` (YAML-сценарии в `call_agent/scenarios/`), `dialog_engine.py` (реплики из `persona/replies.yaml`), `tts_service.py` (Silero, WAV-кэш), `recorder.py` (запись → MinIO `calls/` → обычный pipeline chain). Всё блокирующее в endpoint'е обёрнуто `asyncio.to_thread()`. Модели живут в volume `models_cache`: `vosk/<model>/am/final.mdl` и `silero/v4_ru.pt` — образ их не содержит, проверка на старте роняет контейнер с инструкцией по скачиванию. Опционально `N8N_CALL_ALERT_WEBHOOK_URL` — если задан, после каждого звонка `_finalize` в `call_agent/main.py` шлёт best-effort webhook `{call_id, verdict}` на этот URL (обычно локальный n8n: `http://n8n:5678/webhook/call-alert`); сам workflow — `n8n/workflows/call-alert-telegram.json`, импортировать и активировать вручную через n8n UI (http://localhost:5678).

**MCP-сервер** — `mcp_server/server.py` (FastMCP, stdio), конфиг `.mcp.json` в корне.
Работает на хосте, ходит в Postgres через localhost:5432. Инструменты:
search_transcripts, get_transcript, list_recent_calls, get_call, call_stats,
list_recordings, list_speakers, get_speaker_info, analytics_summary,
frequent_words, frequent_speakers, uploads_over_time.
Требует `pip install -r mcp_server/requirements.txt` на хосте и запущенный
контейнер postgres. Пакет `mcp` не входит в основной requirements.txt намеренно.

HTTP-режим (для команды): сервис `mcp-server` в docker-compose, порт 8200,
образ FROM asr-app (пересборка: `docker compose build api && docker compose
build mcp-server`). Обязателен `MCP_AUTH_TOKEN` в .env — без него контейнер
не стартует. Подключение: `claude mcp add --transport http asr-remote
http://<host>:8200/mcp --header "Authorization: Bearer <токен>"`.

**Admin env vars** (обязательны для запуска admin-функционала):
- `ADMIN_JWT_SECRET` — секрет подписи JWT (обязателен, не должен быть пустым в prod)
- `ADMIN_JWT_TTL_HOURS` — TTL токена (по умолчанию `8`)
- `ADMIN_BOOTSTRAP_LOGIN` / `ADMIN_BOOTSTRAP_PASSWORD` — учётка первого супер-админа (создаётся на startup, если `admin_users` пуста; минимум 8 символов)
- `CORS_ORIGINS` — разрешённые origin для CORS (по умолчанию `http://localhost:5173`)
- `VITE_API_BASE_URL` — URL бэкенда для фронтенда (по умолчанию пусто = тот же хост)
- `VITE_CALL_AGENT_WS` — WS-адрес call-agent для симулятора (build-arg фронтенда, по умолчанию `ws://localhost:8100/ws/call`)

## Pitfalls

- `PIPELINE_MODE` env var is ignored — the monolith path was deleted. Only the chain exists.
- `database/repository.py` does not exist. Use `database/crud.py`.
- Runtime is fully offline (`HF_HUB_OFFLINE=1`). `HF_TOKEN` is build-time only.
- `frontend/nginx.conf` ставит CSP: в `connect-src` обязательны `ws: wss:`, иначе браузер молча блокирует WebSocket симулятора («Ошибка подключения к агенту»).
- Whisper не принимает `"auto"` как код языка — везде маппить в `None` (см. `_get_default_language` в `api/routes/transcriptions.py`).
- Настройки платформы: пустая строка = «не задано» и валидна для любого `value_type` (`_validate_setting_value` в `database/crud.py`). SettingsPage шлёт все поля разом — не ужесточать валидацию пустых.
- `docker compose exec -T postgres psql ...` из PowerShell глотает stdout — выполнять такие команды через Git Bash.
