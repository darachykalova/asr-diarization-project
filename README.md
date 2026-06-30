# Audio Intelligence API — ASR, Diarization & Search

Asynchronous audio processing platform: speech recognition, speaker diarization,
cross-recording speaker identification, and transcript search (keyword / semantic /
hybrid). Runs fully containerized with Docker Compose, behind nginx with TLS.

---

## Capabilities

| Area | What it does |
|------|--------------|
| **ASR** | faster-whisper transcription with word-level timestamps, automatic language detection (multilingual); long audio (>6 min) split into 5-min chunks at pyannote VAD silence boundaries — each chunk gets its own SNR analysis and Whisper model (tiny / base / large-v2); user override via `?whisper_model=` dropdown |
| **Diarization** | pyannote.audio 3.1 — detects who spoke when, assigns `SPEAKER_00`, `SPEAKER_01`, ... |
| **Speaker identification** | SpeechBrain ECAPA-TDNN voice embeddings (192-dim) match the same person across different recordings |
| **Overlap detection** | flags segments where speakers talk over each other |
| **Search** | keyword, semantic (sentence-transformers), and hybrid search over all transcripts or a single job |
| **Export** | transcript export to TXT, SRT, VTT |
| **Async processing** | Celery + Redis, prefork workers, retry policy + dead-letter queue |
| **Storage** | PostgreSQL (metadata), MinIO (audio + ML models), Qdrant (text + voice vectors) |
| **Security** | API-key auth with scopes (read/write/admin), per-key rate limiting, TLS via nginx |
| **Ops** | `/healthz`, `/readyz`, Prometheus `/metrics`, JSON structured logs, webhook notifications, scheduled backups |

---

## Architecture

```text
                         HTTPS (443)
                              │
                          ┌───▼────┐
                          │ nginx  │  TLS termination
                          └───┬────┘
                              │
                          ┌───▼────┐
                          │FastAPI │  api (uvicorn)
                          └───┬────┘
            ┌─────────────────┼──────────────────┐
            │                 │                  │
       ┌────▼────┐       ┌────▼────┐        ┌────▼────┐
       │PostgreSQL│      │  MinIO  │        │  Redis  │
       │ metadata │      │ audio + │        │ broker  │
       │          │      │ models  │        └────┬────┘
       └──────────┘      └─────────┘             │
                                            ┌────▼─────────┐
                                            │ Celery worker│  prefork ×2
                                            └────┬─────────┘
        ┌──────────────┬──────────────┬──────────┴───────┐
        │              │              │                  │
  ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼──────┐    ┌──────▼──────┐
  │  faster-  │  │ pyannote  │  │ SpeechBrain│    │  sentence-  │
  │  whisper  │  │diarization│  │ ECAPA-TDNN │    │ transformers│
  └───────────┘  └───────────┘  └────────────┘    └─────────────┘
                              │
                         ┌────▼────┐
                         │ Qdrant  │  transcript + voice vectors
                         └─────────┘
```

---

## Technology stack

- **API**: Python 3.12, FastAPI, Uvicorn, nginx (TLS)
- **ASR / diarization**: faster-whisper, pyannote.audio 4.0.5
- **Embeddings**: SpeechBrain ECAPA-TDNN (voice), sentence-transformers (text)
- **Async**: Celery 5.6, Redis
- **Data**: PostgreSQL 16, MinIO, Qdrant
- **Security/ops**: slowapi (rate limiting), prometheus-fastapi-instrumentator
- **Infra**: Docker, Docker Compose

---

## Quick start (Docker)

Everything runs in containers. You only need Docker Desktop and a Hugging Face token.

### 1. Prerequisites

- Docker Desktop (WSL2 backend on Windows, **6 GB RAM** allocated — see note below)
- A Hugging Face account with accepted licences for:
  - `pyannote/speaker-diarization-3.1`
  - `pyannote/segmentation-3.0`

### 2. Configure environment

Create a `.env` file in the project root:

```env
POSTGRES_DB=asr_db
POSTGRES_USER=asr_user
POSTGRES_PASSWORD=asr_password

DATABASE_URL=postgresql+psycopg://asr_user:asr_password@postgres:5432/asr_db
REDIS_URL=redis://redis:6379/0
REDIS_BACKEND_URL=redis://redis:6379/1

QDRANT_HOST=qdrant
QDRANT_PORT=6333

MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=admin
MINIO_SECRET_KEY=admin12345
MINIO_BUCKET=audio-files
MINIO_MODELS_BUCKET=ml-models

HF_TOKEN=hf_your_token_here
SPEAKER_MATCH_THRESHOLD=0.70
LOG_LEVEL=INFO
```

> `.env` is git-ignored and must never be committed.

### 3. Build and start

Pass `HF_TOKEN` at build time so gated pyannote models are baked into the image:

```bash
docker compose build --build-arg HF_TOKEN=hf_your_token_here
docker compose up -d
```

Models (faster-whisper, pyannote, SpeechBrain, sentence-transformers) are downloaded
**once at build time** into the image and a Docker volume. At runtime the containers
run with `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` — they never call out to
huggingface.co.

### 4. Verify

```bash
docker compose ps          # all services healthy
curl -k https://localhost/healthz
# {"status":"ok","service":"Audio Intelligence API"}
```

| Service | URL |
|---------|-----|
| API (Swagger) | `https://localhost/docs` |
| Qdrant dashboard | `http://localhost:6333/dashboard` |
| MinIO console | `http://localhost:9001` |
| Prometheus (monitoring profile) | `http://localhost:9090` |
| Grafana (monitoring profile) | `http://localhost:3000` |

The TLS certificate is self-signed for `localhost`, so `curl -k` / "click through"
the browser warning is expected.

> **Windows memory note:** pyannote diarization peaks around ~2.5 GB per worker.
> Create `C:\Users\<you>\.wslconfig` with `[wsl2]` `memory=6GB`, then
> `wsl --shutdown` and restart Docker Desktop.

---

## Authentication

All `/v1/*` endpoints (except health) require an API key:

```http
Authorization: Bearer <api_key>
```

Keys are stored in PostgreSQL with a scope (`read` / `write` / `admin`) and a
per-key rate limit. Create the first admin key with the helper script:

```bash
docker compose exec api python scripts/create_api_key.py
```

The raw key is shown once — store it safely.

---

## API endpoints

### Health & ops (no auth)
```http
GET /healthz
GET /readyz
GET /metrics
```

### Transcriptions
```http
POST /v1/transcriptions/upload      # multipart file upload  -> 202
POST /v1/transcriptions/url         # download from URL, then process -> 202
```

### Jobs
```http
GET /v1/jobs/{job_id}               # status + progress (queued/processing/done/failed/partial)
```

### Transcripts
```http
GET    /v1/transcripts                          # paginated list
GET    /v1/transcripts/{job_id}                 # full transcript + speakers[]
GET    /v1/transcripts/{job_id}/segments        # paginated segments
GET    /v1/transcripts/{job_id}/export?format=  # txt | srt | vtt
DELETE /v1/transcripts/{job_id}                 # GDPR delete: DB + MinIO + Qdrant
```

### Search
```http
GET /v1/search?q=...&mode=keyword|semantic|hybrid&job_id=&speaker=&limit=
```

### Speakers
```http
GET    /v1/speakers                 # registry of known speakers
POST   /v1/speakers                 # register (optionally with reference audio)
PATCH  /v1/speakers/{speaker_id}    # rename / merge
DELETE /v1/speakers/{speaker_id}    # remove + purge voice vectors
```

### API keys
```http
POST   /v1/api-keys
GET    /v1/api-keys
DELETE /v1/api-keys/{key_id}
```

Full interactive docs: `https://localhost/docs`.

---

## Processing workflow

1. Client uploads audio → stored in MinIO, job record created (`202 Accepted`).
2. Celery pipeline chain picked up by a prefork worker.
3. Audio normalized to 16 kHz mono WAV.
4. If audio > 6 min: split into ≤5-min chunks at silence boundaries detected by
   pyannote VAD (reuses the cached segmentation model — no extra load). Each chunk
   gets its own SNR analysis → Whisper model selection (tiny / base / large-v2).
   If no VAD silence is found near a boundary, falls back to energy-based detection.
   If audio ≤ 6 min: processed as a single file.
5. faster-whisper transcribes each chunk with word-level timestamps; results merged
   with adjusted timestamps; heaviest model used is recorded in `model_used`.
6. pyannote diarizes the **full** audio → local speaker labels + overlap flags.
7. Speakers aligned to transcript segments.
8. SpeechBrain extracts a voice embedding per local speaker; Qdrant `speaker_voices`
   is searched to resolve a global `speaker_id` (or a new anonymous speaker is created).
9. Text embeddings stored in Qdrant `transcript_segments`.
10. Transcript + segments persisted to PostgreSQL.
11. Optional webhook fired on completion.

---

## Reliability

- **Retry policy** — pipeline tasks auto-retry transient failures (exponential backoff + jitter).
- **Dead-letter queue** — after retries are exhausted the job is routed to the
  `dead_letter` queue, logged, and marked `failed` with `error_code=MAX_RETRIES_EXCEEDED`.
- **Crash safety** — `task_acks_late=True` and `task_reject_on_worker_lost=True`
  so a job killed mid-flight (e.g. OOM) is requeued, not lost.

---

## Performance & hardware limits

### What the system is bound by

Audio processing is a sequential CPU-bound pipeline:

```
Normalize → VAD → Whisper (ASR) → pyannote (diarization) → Alignment → Embeddings
```

Whisper and pyannote together account for ~95% of processing time. Both run neural
network inference on CPU — there is no async or threading trick that speeds them up.
The only way to make a single task faster is more CPU cores or a GPU.

### Measured throughput (CPU-only, no GPU)

Tests run on 8-core laptop, WSL2 allocated 6 cores, Docker worker `concurrency=2`.
Audio file: 15-second MP3.

| Mode | Processing time | Ratio (processing / audio duration) |
|------|----------------|--------------------------------------|
| **Single speaker** (`max_speakers=1`, diarization skipped) | ~107 s | **×7** |
| **Multi-speaker** (pyannote diarization enabled) | ~370 s | **×25** |
| **Combined average** | ~240 s | **×16** |

Two jobs submitted in parallel finish in the same wall time (both workers are busy),
so **throughput doubles** with 2 workers even though individual job time is unchanged.

### Why `max_speakers=1` is 3× faster

When the caller signals a single speaker, pyannote is skipped entirely.
This removes the heaviest step and cuts processing time
from ~370 s to ~107 s for a 15-second clip.

### Hardware limits and concurrency

| Resource | Current | Limit / reason |
|----------|---------|----------------|
| CPU cores (WSL2) | 6 | `processors=6` in `~/.wslconfig`; 2 left for Windows |
| RAM (WSL2) | 6 GB | `memory=6GB` in `~/.wslconfig` |
| Worker concurrency | 2 | Each worker loads all ML models (~1.5 GB each); a 3rd worker would exhaust RAM |
| GPU | none | No NVIDIA GPU — all inference runs on CPU |

**What would actually speed things up:**

| Change | Expected gain |
|--------|--------------|
| NVIDIA GPU (RTX 3060+) | ×10–15 per task |
| More RAM → 3rd worker | +50% throughput (not per-task speed) |
| Whisper `tiny` instead of `base` | ×2 per task, slightly lower accuracy |
| Second machine with its own worker | ×2 throughput (workers share one Redis queue) |

### Worker scaling & model storage

The worker runs `--pool=prefork --concurrency=2 --max-tasks-per-child=10`. Each
process caches its models after the first task (`services/model_cache.py`), so models
are loaded once per process, not per job.

ML models are stored in MinIO (bucket `ml-models`) so that additional workers on other
machines can download them without rebuilding the Docker image:

```bash
# upload models to MinIO once (already done)
docker compose run --rm worker python scripts/upload_models_to_minio.py
```

On startup each worker runs `scripts/sync_models_from_minio.py`: skips download if
models are already present locally, otherwise pulls from MinIO before starting Celery.

### Offline guarantee & model verification

The service **never contacts Hugging Face at runtime** (`HF_HUB_OFFLINE=1` /
`TRANSFORMERS_OFFLINE=1`). All five models are loaded only from the local
`models_cache` volume, so if huggingface.co is down the program keeps working.

The five required models (single source of truth: `services/model_registry.py`):

| Model | Used for | Local path (under `/app/models`) |
|-------|----------|----------------------------------|
| faster-whisper tiny | ASR (clean audio, auto-selected) | `whisper/models--Systran--faster-whisper-tiny` |
| faster-whisper base | ASR (average quality, auto-selected) | `whisper/models--Systran--faster-whisper-base` |
| faster-whisper large-v2 | ASR (noisy audio, auto-selected) | `whisper/models--Systran--faster-whisper-large-v2` |
| pyannote/speaker-diarization-3.1 | diarization | `hf/hub/models--pyannote--speaker-diarization-3.1` |
| pyannote/segmentation-3.0 | diarization (dep) | `hf/hub/models--pyannote--segmentation-3.0` |
| speechbrain/spkrec-ecapa-voxceleb | voice embeddings | `spkrec-ecapa-voxceleb/embedding_model.ckpt` |
| sentence-transformers MiniLM-L12-v2 | semantic search | `hf/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2` |

**Fail-fast verification.** On startup the worker runs `scripts/verify_models.py`
(and the API calls `model_registry.ensure_available()`). If any model is missing
locally the service **refuses to start** with a clear message naming the model and
how to obtain it — instead of failing later with a cryptic offline-cache error.
The same guard runs at the point of use in each model loader.

```bash
# manual check — exits 0 if all present, 1 (with details) if any missing
docker compose exec worker python scripts/verify_models.py
```

**Keeping a local copy that survives `docker compose down -v`.** The models live in
the `models_cache` named volume (wiped by `down -v`) and are mirrored in MinIO. For
an extra host-filesystem backup, export the volume to a folder you control:

```bash
# back up the model volume to ./models_backup on the host
docker run --rm -v asr_diarization_project_models_cache:/models \
  -v "$(pwd)/models_backup:/backup" alpine \
  tar czf /backup/models.tgz -C /models .

# restore later (e.g. after down -v, with no internet)
docker run --rm -v asr_diarization_project_models_cache:/models \
  -v "$(pwd)/models_backup:/backup" alpine \
  tar xzf /backup/models.tgz -C /models
```

---

## Optional profiles

```bash
# Monitoring: Prometheus + Grafana
docker compose --profile monitoring up -d

# Backups: scheduled pg_dump + MinIO mirror (cron, 02:00 daily)
docker compose --profile backup up -d
```

### Monitoring (Prometheus + Grafana)

The API exposes Prometheus metrics at `/metrics` (via
`prometheus-fastapi-instrumentator`). The `monitoring` profile adds two services:

| Service    | URL                     | Login         |
|------------|-------------------------|---------------|
| Prometheus | http://localhost:9090   | —             |
| Grafana    | http://localhost:3000   | `admin` / `admin` |

Grafana is **provisioned automatically** — no manual setup:

- The Prometheus datasource is wired on first boot
  (`monitoring/grafana/provisioning/datasources/`).
- The **ASR API — Overview** dashboard loads on startup
  (`monitoring/grafana/dashboards/api-overview.json`).

The dashboard tracks request rate per endpoint, latency (p50 / p95 / p99),
error rate (4xx / 5xx) and total request volume, all derived from
`http_requests_total` and `http_request_duration_seconds`.

To edit a panel, change the JSON and restart Grafana — the file provider
re-reads dashboards every 30 s.

---

## Load testing

A Postman collection lives in `loadtest/`. See `loadtest/README.md` for setup.
Read-only endpoints sustain ~130 req/sec with 0% errors at 5 virtual users
(target was 50 req/min).

---

## Project structure

```text
api/
├── auth.py                 # API-key auth, scopes
├── main.py                 # FastAPI app, rate limiting, metrics, startup
└── routes/                 # transcriptions, jobs, transcripts, calls,
                            # speakers, search, api_keys, health

services/
├── asr_service.py               # faster-whisper wrapper (cached model)
├── audio_quality_service.py     # SNR estimation, auto model selection
├── chunking_service.py          # split long audio at VAD silence boundaries (pyannote + energy fallback)
├── diarization_service.py       # pyannote wrapper (cached pipeline)
├── voice_embedding_service.py   # SpeechBrain ECAPA-TDNN (192-dim)
├── text_embedding_service.py    # sentence-transformers
├── speaker_identification_service.py
├── alignment_service.py         # map speakers onto transcript segments
├── qdrant_service.py / async_qdrant_service.py
├── model_cache.py               # per-process model singletons
├── webhook_service.py
└── ...

tasks/
├── audio_tasks.py          # build_pipeline_chain, dead-letter task
└── pipeline_tasks.py       # normalize → asr → diarize → merge → persist → identify → finalize
clients/minio_client.py     # MinIO storage + lifecycle
database/
├── models.py               # SQLAlchemy ORM models
├── crud.py                 # all DB read/write functions
├── session.py              # SessionLocal factory
└── init_db.py
schemas/                    # Pydantic request/response models
scripts/
├── create_api_key.py
├── download_models.py            # build-time model download
├── upload_models_to_minio.py     # push models to MinIO
└── sync_models_from_minio.py     # pull models on worker startup

nginx/                      # TLS reverse proxy config + certs (certs git-ignored)
monitoring/                 # Prometheus + Grafana config
backup/                     # backup container (pg_dump + mc mirror)
loadtest/                   # Postman collection + environment
docker-compose.yml
Dockerfile
requirements.txt
```

---

## Troubleshooting

**`HF_TOKEN is not set` / diarization fails**
Rebuild with the token so gated models are baked in:
`docker compose build --build-arg HF_TOKEN=hf_xxx`.

**Worker OOM / killed mid-job**
Raise Docker memory to 6 GB (`.wslconfig` on Windows) and restart Docker Desktop.
Jobs that were processing are requeued automatically (`task_reject_on_worker_lost`).

**nginx 502 after restarting or recreating `api`**
nginx caches the old container IP. Run `docker compose restart nginx` to fix.

**Redis / Qdrant connection errors**
Ensure the full stack is up: `docker compose up -d` and check `docker compose ps`.

---

## Status

All core functional requirements are implemented and verified end-to-end:
async upload, multilingual ASR with word timestamps, diarization, overlap flags,
cross-recording speaker identification, partial results, voice registry, GDPR delete,
webhooks, keyword/semantic/hybrid search, SRT/VTT/TXT export, API-key auth with scopes
and rate limiting, health/readiness probes, Prometheus metrics, structured JSON logs,
scheduled backups, and monitoring.

**Not yet implemented:** stereo-telephony "channel = speaker" mode (FR-8); GPU worker image.
