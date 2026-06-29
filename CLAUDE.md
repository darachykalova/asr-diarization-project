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

## Pitfalls

- `PIPELINE_MODE` env var is ignored — the monolith path was deleted. Only the chain exists.
- `database/repository.py` does not exist. Use `database/crud.py`.
- Runtime is fully offline (`HF_HUB_OFFLINE=1`). `HF_TOKEN` is build-time only.
