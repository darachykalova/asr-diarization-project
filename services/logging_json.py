import json
import logging
import os
import traceback
from datetime import datetime, timezone


_EXTRA_FIELDS = (
    "job_id", "speaker_id", "transcript_id",
    "method", "path", "status", "ip", "api_key_id",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        for key in _EXTRA_FIELDS:
            val = getattr(record, key, None)
            if val is not None:
                obj[key] = val
        return json.dumps(obj, ensure_ascii=False)


def setup_json_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level, logging.INFO))
