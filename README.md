# ASR Diarization & Semantic Search Service

## Overview

This project is an asynchronous audio processing platform that provides:

* Automatic Speech Recognition (ASR)
* Speaker Diarization
* Multilingual Language Detection
* Semantic Search
* Keyword Search
* Hybrid Search
* Vector Storage using Qdrant
* Background Processing using Celery
* Cross-call Speaker Voice Matching
* API Key Authentication

The service allows users to upload audio files, automatically generate speaker-attributed transcripts, store transcript segments in a vector database, and perform semantic retrieval across processed conversations. It also recognizes the same speaker across multiple calls using voice embeddings.

---

# Features

## Audio Processing

* Audio file upload via REST API
* Background task execution using Celery
* Processing status tracking
* Transcript persistence in PostgreSQL
* Audio storage in MinIO

## Speech Recognition

Powered by Faster-Whisper.

Capabilities:

* Automatic language detection
* Word-level timestamps
* Multilingual transcription
* CPU-based inference

Supported languages include:

* English
* Russian
* German
* French
* Spanish

and all languages supported by Whisper.

---

## Speaker Diarization

Powered by pyannote.audio.

Capabilities:

* Automatic speaker detection
* Dynamic number of speakers
* Speaker assignment to transcript segments
* Speaker-aware transcript generation

---

## Speaker Voice Matching

The service supports speaker identification across multiple processed calls.

After diarization, local speaker labels such as `SPEAKER_00` and `SPEAKER_01` are processed independently.

The workflow is:

1. extract the longest speech segment for each local speaker;
2. generate a 512-dimensional voice embedding;
3. search the `speaker_voices` collection in Qdrant;
4. match an existing speaker if similarity is high enough;
5. create a new anonymous speaker if no match is found;
6. store the speaker occurrence in PostgreSQL;
7. update transcript segments with the resolved `speaker_id`.

Current configuration:

```python
VECTOR_SIZE = 512
MATCH_THRESHOLD = 0.90
```

To avoid incorrect merging, the system excludes speakers already assigned inside the same call from the next local speaker matching attempt.

The current local Windows implementation avoids the TorchCodec dependency and uses a stable waveform-based embedding extraction approach.

---

## Semantic Search

Powered by:

* Sentence Transformers
* Qdrant

Model:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Capabilities:

* Semantic similarity search
* Multilingual embeddings
* Search across all conversations
* Search inside a specific job
* Hybrid keyword + semantic ranking

---

# Architecture

```text
                        +----------------+
                        |     Client     |
                        +-------+--------+
                                |
                                v
                        +----------------+
                        |    FastAPI     |
                        +-------+--------+
                                |
        +-----------------------+-----------------------+
        |                       |                       |
        v                       v                       v
+---------------+       +---------------+       +---------------+
|  PostgreSQL   |       |     MinIO     |       |     Redis     |
| Metadata DB   |       | Audio Storage |       | Task Broker   |
+---------------+       +---------------+       +-------+-------+
                                                        |
                                                        v
                                                +---------------+
                                                | Celery Worker |
                                                +-------+-------+
                                                        |
        +-----------------------+-----------------------+-----------------------+
        |                       |                       |                       |
        v                       v                       v                       v
+---------------+       +---------------+       +---------------+       +---------------+
| Faster-Whisper|       |   PyAnnote    |       | Sentence      |       | Voice         |
| ASR           |       | Diarization   |       | Transformers  |       | Matching      |
+---------------+       +---------------+       +---------------+       +---------------+
        |                       |                       |                       |
        +-----------------------+-----------------------+-----------------------+
                                |
                                v
                        +---------------+
                        |    Qdrant     |
                        | Text + Voice  |
                        | Vectors       |
                        +---------------+
```

---

# Project Structure

```text
api/
├── auth.py
├── main.py
└── routes/

database/
├── crud.py
├── database.py
├── init_db.py
├── models.py
├── repository.py
└── session.py

schemas/
├── transcript_schema.py
└── api/

services/
├── alignment_service.py
├── asr_service.py
├── audio_segment_extractor.py
├── audio_service.py
├── diarization_service.py
├── embedding_service.py
├── pipeline_service.py
├── qdrant_service.py
├── reindex_service.py
├── speaker_identification_service.py
├── text_embedding_service.py
├── vad_service.py
├── voice_embedding_service.py
├── webhook_service.py
└── worker_job_service.py

tasks/
├── audio_tasks.py

data/
├── input/
├── normalized/
├── output/
└── temp_voice/

docker-compose.yml
requirements.txt
README.md
```

---

# Technology Stack

## Backend

* Python 3.12
* FastAPI
* Uvicorn

## Speech Processing

* Faster-Whisper
* Pyannote Audio

## Vector Search

* Qdrant
* Sentence Transformers

## Database and Storage

* PostgreSQL
* MinIO

## Authentication

* API Key authentication
* Bearer token authorization

## Background Processing

* Celery
* Redis

## Infrastructure

* Docker
* Docker Compose

---

# Installation

## Clone Repository

```bash
git clone <repository-url>
cd asr_diarization_project
```

## Create Virtual Environment

```bash
python -m venv venv
```

## Activate Environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Infrastructure Setup

Start all infrastructure services:

```bash
docker compose up -d
```

The project uses:

* PostgreSQL — metadata storage
* Redis — Celery broker
* Qdrant — vector database
* MinIO — object storage

Verify services:

```bash
docker ps
```

Qdrant:

```text
http://localhost:6333/dashboard
```

MinIO Console:

```text
http://localhost:9001
```

PostgreSQL:

```bash
docker exec -it asr_diarization_project-postgres-1 psql -U asr_user -d asr_db
```

---

# Hugging Face Token

Speaker diarization requires a Hugging Face access token.

PowerShell:

```powershell
$env:HF_TOKEN="your_hugging_face_token"
```

The token must have access to:

* pyannote/speaker-diarization-3.1
* pyannote/segmentation-3.0

The token is required for PyAnnote diarization models.

Voice matching in the current Windows-compatible local implementation does not require TorchCodec.

---

# Running the Application

## Start Celery Worker

```bash
celery -A tasks.audio_tasks worker --loglevel=info --pool=solo
```

## Start FastAPI

Open a second terminal:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

# Quick Start

Open three terminals.

### Terminal 1 — Infrastructure

```bash
docker compose up -d
```

### Terminal 2 — Celery Worker

```powershell
$env:HF_TOKEN="your_hugging_face_token"

celery -A tasks.audio_tasks worker --loglevel=info --pool=solo
```

### Terminal 3 — FastAPI

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

After startup:

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Qdrant Dashboard:

```text
http://localhost:6333/dashboard
```

---

# API Documentation

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

---

# API Authentication

Protected endpoints require an API key.

Authorization format:

```http
Authorization: Bearer <api_key>
```

API keys are stored in PostgreSQL.

A helper script can be used to create API keys:

```bash
python scripts/create_api_key.py
```

Use the generated raw key only once and store it safely.

---

# API Endpoints

## Health

```http
GET /
```

## Transcriptions

```http
POST /v1/transcriptions/upload
```

## Jobs

```http
GET /v1/jobs/{job_id}
```

## Transcripts

```http
GET /v1/transcripts/{job_id}
DELETE /v1/transcripts/{job_id}
```

## Calls

```http
GET /v1/calls/{job_id}
GET /v1/calls/search
```

## Speakers

```http
GET /v1/speakers
POST /v1/speakers
PATCH /v1/speakers/{speaker_id}
DELETE /v1/speakers/{speaker_id}
```

## API Keys

```http
POST /v1/api-keys
GET /v1/api-keys
DELETE /v1/api-keys/{key_id}
```

---

# Processing Workflow

1. Upload audio file.
2. Store audio in MinIO and create job record.
3. Create processing task.
4. Execute transcription.
5. Execute speaker diarization.
6. Align speakers with transcript segments.
7. Generate text embeddings.
8. Extract voice embeddings and resolve speaker identity.
9. Store transcript segments in Qdrant.
10. Return transcript and search availability.

---

# Search Modes

## Keyword Search

Exact text matching.

Example:

```text
мошенники
```

---

## Semantic Search

Embedding similarity search.

Example:

```text
обман
```

Can return:

```text
Это мошенники
Не дайте себя обмануть
```

---

## Hybrid Search

Combines:

* keyword relevance
* semantic similarity

Provides the most accurate ranking.

---

# Search Scope

The search endpoint supports two modes.

### Global Search

Search across all processed conversations.

```text
job_id = null
```

### Job-Specific Search

Search inside a single conversation.

```text
job_id = <job_uuid>
```

---

# Output Artifacts

For every processed job the system stores:

* uploaded audio in MinIO
* normalized audio
* transcript JSON
* job status in PostgreSQL
* transcript segments in PostgreSQL
* transcript vectors in Qdrant
* speaker occurrences in PostgreSQL
* speaker voice vectors in Qdrant

Main Qdrant collections:

```text
transcript_segments
speaker_voices
```

---

# Troubleshooting

## HF_TOKEN is not set

Speaker diarization models cannot be loaded.

Solution:

```powershell
$env:HF_TOKEN="your_hugging_face_token"
```

---

## Redis Connection Error

Verify that Redis is running:

```bash
docker compose up -d
```

---

## Qdrant Connection Error

Verify that Qdrant is available:

```text
http://localhost:6333/dashboard
```

---

## mkl_malloc: failed to allocate memory

The machine does not have enough RAM for the selected Whisper model.

Possible solutions:

* Use a smaller model (`tiny` or `base`)
* Close memory-intensive applications
* Increase available system memory

---

## TorchCodec Error on Windows

If TorchCodec breaks startup or speaker matching, remove it:

```powershell
pip uninstall torchcodec -y
```

The local Windows setup uses:

```text
torch==2.11.0
torchaudio==2.11.0
```

Do not install speechbrain or torchcodec for the current local Windows configuration.

## Voice Matching Does Not Match Speakers

Check Celery logs for:

```text
Voice embedding extracted: dim=512
matched SPEAKER_00 to speaker_id=...
```

Check PostgreSQL:

```sql
SELECT *
FROM occurrences
ORDER BY id DESC
LIMIT 12;
```

---

# Current Status

The project is fully functional and currently supports:

* asynchronous audio processing
* audio upload through REST API
* MinIO audio object storage
* PostgreSQL metadata storage
* Redis-based task queue
* Celery background processing
* multilingual speech recognition
* voice activity detection
* speaker diarization
* transcript generation
* speaker-aware transcript segments
* semantic search
* keyword search
* hybrid search
* Qdrant vector storage
* API key authentication
* transcript deletion
* pagination for call segments
* speaker management
* speaker occurrence tracking
* cross-call speaker voice matching
* webhook notifications

---

# Future Improvements

Potential future improvements:

* speaker profile management UI
* improved production-grade speaker embedding backend
* better confidence calibration
* LLM-based transcript enrichment
* transcript summarization
* sentiment analysis
* conversation analytics dashboards
* real-time streaming transcription
* GPU worker scaling
* advanced monitoring and observability
