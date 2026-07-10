# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Rebuild after code changes (COPY bakes code into image — restart alone is not enough)
docker compose build api worker && docker compose up -d api worker

# Tests (no containers required)
python -m pytest tests/
python -m pytest tests/test_api.py::test_health_check   # single test

# First-time setup
docker compose build --build-arg HF_TOKEN=hf_xxx
docker compose exec api python scripts/create_api_key.py
docker compose exec worker python scripts/verify_models.py

# Admin console — первый запуск
docker compose exec api python scripts/bootstrap_admin.py --login admin --role super_admin
# (пароль берётся из --password или env ADMIN_BOOTSTRAP_PASSWORD или интерактивно)

# Frontend (dev)
cd frontend && npm install && npm run dev   # http://localhost:5173

# Frontend (prod build)
cd frontend && npm run build               # dist/ → раздаётся nginx (docker compose up -d frontend)
docker compose up -d frontend
```

## Architecture

**One image (`asr-app`), two roles:** `api` (FastAPI + Uvicorn) queues jobs; `worker` (Celery prefork, concurrency=2) runs them.

**Pipeline chain** — assembled in `tasks/audio_tasks.py:build_pipeline_chain()`, executed in `tasks/pipeline_tasks.py`. Each task passes a `ctx` dict to the next. Context keys per task are documented at the top of `pipeline_tasks.py`.

```
normalize → asr → diarize → merge_align → persist → identify_speakers → finalize
```

**Chunking + auto model selection** — `asr_task` calls `chunking_service.split_audio()` for audio >6 min. Splits at VAD silence boundaries (pyannote `_segmentation`, already cached) with energy fallback. Each chunk gets its own SNR → Whisper model (tiny/base/large-v2). Diarization always runs on the full file.

**Model cache** — `services/model_cache.py` stores all ML models in module-level globals per worker process (load once, reuse across jobs). Startup refuses if any of the 5 required models are missing locally (`services/model_registry.py`).

**DB layer** — all ops in `database/crud.py`. Celery task functions take `db: Session` (caller manages). Transcript query functions (used by API routes) manage `SessionLocal()` internally. `database/repository.py` was deleted.

**Auth** — `api/auth.py`, Bearer token with scope `read`/`write`/`admin`. Test override: `app.dependency_overrides[verify_api_key] = lambda: mock_key`.

**Admin console** — веб-интерфейс в `frontend/` (React+Vite). Отдельный JWT-слой в `api/auth_users.py` (не пересекается с API-key auth). Маршруты под `/v1/admin/*` подключены через `api/routes/admin_router.py`. Роли: `moderator` (аудио+транскрипции), `super_admin` (+ пользователи, аудит, настройки). Тест-оверрайд: `app.dependency_overrides[get_current_user] = lambda: mock_admin`.

**Admin env vars** (обязательны для запуска admin-функционала):
- `ADMIN_JWT_SECRET` — секрет подписи JWT (обязателен, не должен быть пустым в prod)
- `ADMIN_JWT_TTL_HOURS` — TTL токена (по умолчанию `8`)
- `ADMIN_BOOTSTRAP_LOGIN` / `ADMIN_BOOTSTRAP_PASSWORD` — учётка первого супер-админа (создаётся на startup, если `admin_users` пуста; минимум 8 символов)
- `CORS_ORIGINS` — разрешённые origin для CORS (по умолчанию `http://localhost:5173`)
- `VITE_API_BASE_URL` — URL бэкенда для фронтенда (по умолчанию пусто = тот же хост)

## Pitfalls

- `PIPELINE_MODE` env var is ignored — the monolith path was deleted. Only the chain exists.
- `database/repository.py` does not exist. Use `database/crud.py`.
- Runtime is fully offline (`HF_HUB_OFFLINE=1`). `HF_TOKEN` is build-time only.
