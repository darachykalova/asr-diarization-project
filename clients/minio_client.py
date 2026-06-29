import logging
import os
from pathlib import Path

from minio import Minio
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration
from minio.commonconfig import ENABLED, Filter

logger = logging.getLogger(__name__)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "admin12345")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "audio-files")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"
_AUDIO_TTL_DAYS = int(os.getenv("AUDIO_TTL_DAYS", "90"))


class MinioStorageClient:
    def __init__(self):
        self.bucket_name = MINIO_BUCKET

        self.client = Minio(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE
        )

        self.ensure_bucket_exists()

    def ensure_bucket_exists(self) -> None:
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)
        self._apply_lifecycle()

    def _apply_lifecycle(self) -> None:
        if _AUDIO_TTL_DAYS <= 0:
            return
        try:
            config = LifecycleConfig(
                [
                    Rule(
                        ENABLED,
                        rule_filter=Filter(prefix="jobs/"),
                        rule_id="audio-ttl",
                        expiration=Expiration(days=_AUDIO_TTL_DAYS),
                    )
                ]
            )
            self.client.set_bucket_lifecycle(self.bucket_name, config)
        except Exception as exc:
            logger.warning("Failed to set MinIO lifecycle policy: %s", exc)

    def upload_file(
        self,
        local_path: str,
        object_key: str,
        content_type: str | None = None
    ) -> str:
        self.client.fput_object(
            bucket_name=self.bucket_name,
            object_name=object_key,
            file_path=local_path,
            content_type=content_type
        )

        return object_key

    def download_file(
        self,
        object_key: str,
        local_path: str
    ) -> str:
        Path(local_path).parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.client.fget_object(
            bucket_name=self.bucket_name,
            object_name=object_key,
            file_path=local_path
        )

        return local_path

    def delete_file(
        self,
        object_key: str | None
    ) -> bool:
        if not object_key:
            return False

        self.client.remove_object(
            bucket_name=self.bucket_name,
            object_name=object_key
        )

        return True
