"""
Startup script: ensure ML models are available in /app/models.

Priority:
  1. Models already present locally → skip everything.
  2. Local archive models_backup/models.tgz → extract.
  3. MinIO ml-models bucket → download file-by-file.
  4. None of the above → exit 1 (worker cannot start).

Runs automatically before the Celery worker (and API) start.
"""

import logging
import os
import sys
import tarfile
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
LOCAL_ARCHIVE    = Path(os.getenv("MODELS_ARCHIVE_PATH", "/app/models_backup/models.tgz"))

# Sentinel paths (corrected to the real on-disk layout): if ALL exist locally,
# models are already present and the MinIO sync can be skipped.
_SENTINELS = [
    "whisper/models--Systran--faster-whisper-base",
    "spkrec-ecapa-voxceleb/embedding_model.ckpt",
    "hf/hub/models--pyannote--speaker-diarization-3.1",
    "hf/hub/models--pyannote--segmentation-3.0",
    "hf/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2",
]


def models_already_present() -> bool:
    for sentinel in _SENTINELS:
        p = LOCAL_MODELS_DIR / sentinel
        if not (p.exists() and any(p.rglob("*")) if p.is_dir() else p.exists()):
            return False
    logger.info("All models already present locally. Skipping MinIO download.")
    return True


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


def extract_from_local_archive() -> bool:
    if not LOCAL_ARCHIVE.exists():
        return False
    logger.info("Found local archive %s — extracting to %s ...", LOCAL_ARCHIVE, LOCAL_MODELS_DIR)
    LOCAL_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(LOCAL_ARCHIVE, "r:gz") as tar:
        tar.extractall(LOCAL_MODELS_DIR)
    logger.info("Extraction from local archive complete.")
    return True


def main() -> None:
    # 1. Already present?
    if models_already_present():
        sys.exit(0)

    # 2. Local archive?
    if extract_from_local_archive():
        if models_already_present():
            sys.exit(0)
        logger.error("Archive extracted but sentinels still missing — archive may be corrupt.")
        sys.exit(1)

    # 3. MinIO?
    logger.info("No local archive found. Connecting to MinIO at %s ...", MINIO_ENDPOINT)
    try:
        client = get_client()
        if not client.bucket_exists(MODELS_BUCKET):
            logger.error("MinIO bucket '%s' does not exist. Cannot obtain models.", MODELS_BUCKET)
            sys.exit(1)
    except Exception as e:
        logger.error("Cannot connect to MinIO: %s. Cannot obtain models.", e)
        sys.exit(1)

    downloaded = download_models(client)
    logger.info("MinIO sync complete. Downloaded: %d files.", downloaded)

    if not models_already_present():
        logger.error("Models still missing after MinIO sync. Check bucket contents.")
        sys.exit(1)


if __name__ == "__main__":
    main()
