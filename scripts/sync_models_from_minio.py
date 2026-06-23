"""
Startup script: download ML models from MinIO to /app/models if missing locally.

Runs automatically before the Celery worker starts (see docker-compose.yml).
If MinIO bucket doesn't exist or is empty, exits without error so the worker
can still use models baked into the image/volume.
"""

import logging
import os
import sys
from pathlib import Path

from minio import Minio
from minio.error import S3Error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT",  "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "admin12345")
MINIO_SECURE     = os.getenv("MINIO_SECURE", "false").lower() == "true"
MODELS_BUCKET    = os.getenv("MINIO_MODELS_BUCKET", "ml-models")
LOCAL_MODELS_DIR = Path(os.getenv("MODEL_CACHE_DIR", "/app/models"))

# Sentinel paths: if these exist locally, models are already present.
_SENTINELS = [
    "whisper/base",
    "spkrec-ecapa-voxceleb",
    "hf/models--pyannote--speaker-diarization-3.1",
]


def models_already_present() -> bool:
    for sentinel in _SENTINELS:
        p = LOCAL_MODELS_DIR / sentinel
        if p.exists() and any(p.rglob("*")):
            logger.info("Models already present locally (%s exists). Skipping download.", sentinel)
            return True
    return False


def get_client() -> Minio:
    return Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def download_models(client: Minio) -> int:
    try:
        objects = list(client.list_objects(MODELS_BUCKET, recursive=True))
    except S3Error as e:
        logger.warning("Cannot list MinIO bucket '%s': %s. Using local models.", MODELS_BUCKET, e)
        return 0

    if not objects:
        logger.warning("MinIO bucket '%s' is empty. Using local models.", MODELS_BUCKET)
        return 0

    downloaded = 0
    total = len(objects)
    logger.info("Downloading %d model files from MinIO...", total)

    for i, obj in enumerate(objects, 1):
        local_path = LOCAL_MODELS_DIR / obj.object_name
        if local_path.exists():
            continue

        local_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("[%d/%d] %s (%.1f MB)", i, total, obj.object_name, (obj.size or 0) / 1_048_576)
        client.fget_object(MODELS_BUCKET, obj.object_name, str(local_path))
        downloaded += 1

    return downloaded


def main() -> None:
    if models_already_present():
        sys.exit(0)

    logger.info("Local models not found. Connecting to MinIO at %s ...", MINIO_ENDPOINT)

    try:
        client = get_client()
        if not client.bucket_exists(MODELS_BUCKET):
            logger.warning("MinIO bucket '%s' does not exist yet. Using local models.", MODELS_BUCKET)
            sys.exit(0)
    except Exception as e:
        logger.warning("Cannot connect to MinIO: %s. Continuing without sync.", e)
        sys.exit(0)

    downloaded = download_models(client)
    logger.info("Sync complete. Downloaded: %d files.", downloaded)


if __name__ == "__main__":
    main()
