# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Build & run
```bash
# First-time build (bakes models into image at build time)
docker compose build --build-arg HF_TOKEN=hf_xxx

# Start everything
docker compose up -d

# Rebuild after code changes (code is COPYed into the image — restart alone is NOT enough)
docker compose build api worker
docker compose up -d api worker

# Tail logs
docker compose logs -f api
docker compose logs -f worker
```

### Tests
```bash
# Run all tests (from project root, no Docker needed)
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_api.py

# Run a single test
python -m pytest tests/test_api.py::test_health_check
```

Tests use `fastapi.testclient.TestClient` and `unittest.mock`. They do not require running containers.

### Useful one-liners
```bash
# Check API is ready
curl -k https://localhost/readyz

# Create admin API key (run once after first docker compose up)
docker compose exec api python scripts/create_api_key.py

# Verify all ML models are present locally
docker compose exec worker python scripts/verify_models.py

# Upload models to MinIO (so other workers can pull them without rebuilding)
docker compose run --rm worker python scripts/upload_models_to_minio.py
```

---

## Architecture

### Two services, one image (`asr-app`)

The same Docker image runs as:
- **`api`** — FastAPI + Uvicorn, handles HTTP, queues Celery tasks
- **`worker`** — Celery prefork worker (`concurrency=2`), runs the audio pipeline

### Request lifecycle

```
POST /v1/transcriptions/upload
  → save audio to MinIO
  → create Job + Recording rows in PostgreSQL
  → build_pipeline_chain().apply_async()   ← tasks/audio_tasks.py
  → return 202 { job_id }

GET /v1/jobs/{job_id}   ← polls status
GET /v1/transcripts/{job_id}   ← reads result
```

### Celery pipeline chain (`tasks/pipeline_tasks.py`)

Each task receives a `ctx` dict from the previous task and returns an enriched `ctx`. Context keys added by each step are documented at the top of `pipeline_tasks.py`.

```
normalize_task → asr_task → diarize_task → merge_align_task
→ persist_task → identify_speakers_task → finalize_task
```

`build_pipeline_chain()` in `tasks/audio_tasks.py` assembles the chain. `chain_error_handler` in `pipeline_tasks.py` catches any failure and marks the job `failed`.

### ASR with per-chunk model selection (`services/chunking_service.py`)

Audio > 6 min is split into ≤5-min chunks **before** ASR:
1. `chunking_service.split_audio()` runs pyannote VAD (reuses the cached `_segmentation` model) to find silence regions, then cuts at the nearest silence to each 5-min boundary. Falls back to energy-based detection if VAD fails.
2. Each chunk gets its own `compute_snr_db()` → `select_model_by_snr()` → Whisper model.
3. Timestamps are shifted by the chunk's `offset_sec` before merging.
4. `model_used` stored in DB is the heaviest model used across all chunks.

Diarization always runs on the **full** audio file (after chunked ASR).

### Model caching (`services/model_cache.py`)

Worker processes cache all ML models in module-level globals after first load. Models are never reloaded between jobs within the same worker process. The cache holds: Whisper models (by size), pyannote pipeline, SpeechBrain embedder, SentenceTransformer.

At startup the worker verifies all 5 required models are present locally (`services/model_registry.py`); the service refuses to start if any are missing.

### Database layer (`database/crud.py`)

All DB operations live in `database/crud.py` as plain functions:
- Functions used by **Celery tasks** take `db: Session` as a parameter (caller manages session).
- Functions used by **API routes** (transcript queries) manage their own `SessionLocal()` internally — routes call them without passing a session.

`database/repository.py` does not exist (was consolidated into `crud.py`).

### Auth (`api/auth.py`)

All `/v1/*` routes require `Authorization: Bearer <key>`. Keys are stored in PostgreSQL with a scope (`read`/`write`/`admin`). Override for tests: `app.dependency_overrides[verify_api_key] = lambda: mock_key`.

### Key env vars

| Var | Purpose |
|-----|---------|
| `PIPELINE_MODE` | Legacy — ignored, chain is always used |
| `HF_TOKEN` | Hugging Face token (build-time only; runtime is offline) |
| `SPEAKER_MATCH_THRESHOLD` | Qdrant cosine similarity threshold for speaker ID (default 0.70) |
| `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` | Set to `1` at runtime — no HF calls ever |

### What NOT to do

- Do not `docker compose restart api` after code changes — the image bakes code via `COPY`. Always rebuild: `docker compose build api && docker compose up -d api`.
- Do not add a `PIPELINE_MODE` branch — the monolith path was deleted; only the chain pipeline exists.
- Do not import from `database.repository` — it was deleted; use `database.crud`.
- Do not add `get_occurrences_by_speaker` to `crud.py` — it already exists (was duplicated once, fixed).
