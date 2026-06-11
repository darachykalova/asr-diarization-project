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

The service allows users to upload audio files, automatically generate speaker-attributed transcripts, store transcript segments in a vector database, and perform semantic retrieval across processed conversations.

---

# Features

## Audio Processing

* Audio file upload via REST API
* Background task execution using Celery
* Processing status tracking
* Transcript persistence

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
Client
   |
   v
FastAPI
   |
   v
Redis
   |
   v
Celery Worker
   |
   +--> Faster Whisper
   |
   +--> Pyannote Diarization
   |
   +--> Sentence Transformers
   |
   +--> Qdrant
```

---

# Project Structure

```text
api/
├── main.py
├── routes/
│   ├── calls.py
│   ├── health.py
│   ├── jobs.py
│   ├── transcripts.py
│   └── transcriptions.py

schemas/
├── transcript_schema.py
└── api/
    ├── call_schema.py
    ├── job_schema.py
    └── transcription_schema.py

services/
├── asr_service.py
├── diarization_service.py
├── pipeline_service.py
├── qdrant_service.py
├── text_embedding_service.py
└── worker_job_service.py

data/
├── input/
└── output/

celery_app.py
tasks.py
Dockerfile
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

Start Redis and Qdrant:

```bash
docker compose up -d
```

Verify services:

Qdrant Dashboard:

```text
http://localhost:6333/dashboard
```

Redis:

```text
localhost:6379
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

---

# Running the Application

## Start Celery Worker

```bash
python -m celery -A tasks worker --loglevel=info --pool=solo --concurrency=1
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

python -m celery -A tasks worker --loglevel=info --pool=solo
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

# API Endpoints

## Health

```http
GET /
```

## Transcriptions

```http
POST /transcriptions
POST /transcriptions/upload
```

## Jobs

```http
GET /jobs/{job_id}
```

## Transcripts

```http
GET /transcripts/{job_id}
```

## Calls

```http
GET /calls/{job_id}
GET /calls/search
```

---

# Processing Workflow

1. Upload audio file.
2. Create processing task.
3. Execute transcription.
4. Execute speaker diarization.
5. Align speakers with transcript segments.
6. Generate embeddings.
7. Store transcript segments in Qdrant.
8. Return transcript and search availability.

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

```text
transcript.json
job_status.json
```

and indexed transcript segments inside Qdrant.

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

# Current Status

The project is fully functional and supports:

* asynchronous audio processing
* multilingual speech recognition
* speaker diarization
* transcript generation
* semantic search
* hybrid search
* vector storage and retrieval

Future improvements may include:

* PostgreSQL metadata storage
* speaker voice embeddings
* speaker identification across conversations
* LLM-based transcript enrichment
* advanced analytics
