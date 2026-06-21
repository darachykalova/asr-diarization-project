FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --timeout=300 --retries=10 -r requirements.txt

# All HuggingFace downloads (faster-whisper, pyannote, sentence-transformers) go here.
# SpeechBrain uses MODEL_CACHE_DIR explicitly in the service code.
ENV HF_HOME=/app/models/hf
ENV MODEL_CACHE_DIR=/app/models

# Copy download script before the full source copy so Docker can cache the
# model layer independently of source code changes.
COPY scripts/download_models.py scripts/download_models.py

# Pass HF_TOKEN at build time to pre-download gated pyannote model:
#   docker compose build --build-arg HF_TOKEN=hf_xxx
# Without it, pyannote is skipped here and downloaded on first container run.
ARG HF_TOKEN=""
RUN HF_TOKEN="$HF_TOKEN" python scripts/download_models.py

COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
