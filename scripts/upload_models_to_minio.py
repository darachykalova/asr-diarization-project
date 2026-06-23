"""
One-time script: upload all ML models from /app/models to MinIO bucket ml-models.

Run inside the worker container after first build:
  docker compose run --rm worker python scripts/upload_models_to_minio.py
"""

import logging
import os
import sys
from pathlib import Path

from minio import Minio

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


def get_client() -> Minio:
    return Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE,
    )


def ensure_bucket(client: Minio) -> None:
    if not client.bucket_exists(MODELS_BUCKET):
        client.make_bucket(MODELS_BUCKET)
        logger.info("Created bucket: %s", MODELS_BUCKET)
    else:
        logger.info("Bucket already exists: %s", MODELS_BUCKET)


def upload_models(client: Minio) -> int:
    if not LOCAL_MODELS_DIR.exists():
        logger.error("Models directory not found: %s", LOCAL_MODELS_DIR)
        sys.exit(1)

    uploaded = 0
    skipped = 0

    for local_file in sorted(LOCAL_MODELS_DIR.rglob("*")):
        if not local_file.is_file():
            continue

        object_name = local_file.relative_to(LOCAL_MODELS_DIR).as_posix()

        try:
            client.stat_object(MODELS_BUCKET, object_name)
            skipped += 1
            continue
        except Exception:
            pass

        logger.info("Uploading %s (%s MB)...", object_name, round(local_file.stat().st_size / 1_048_576, 1))
        client.fput_object(
            bucket_name=MODELS_BUCKET,
            object_name=object_name,
            file_path=str(local_file),
        )
        uploaded += 1

    return uploaded, skipped


def main() -> None:
    logger.info("Connecting to MinIO at %s ...", MINIO_ENDPOINT)
    client = get_client()
    ensure_bucket(client)

    logger.info("Scanning %s ...", LOCAL_MODELS_DIR)
    uploaded, skipped = upload_models(client)

    logger.info("Done. Uploaded: %d files, skipped (already exist): %d files", uploaded, skipped)


if __name__ == "__main__":
    main()
