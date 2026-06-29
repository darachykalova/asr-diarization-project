import hashlib
import hmac
import json
import logging
import os
import time

import httpx


logger = logging.getLogger(__name__)

WEBHOOK_SECRET = os.getenv(
    "WEBHOOK_SECRET",
    "changeme-set-in-env"
)


def send_webhook(
    url: str,
    payload: dict,
    max_retries: int = 3
) -> bool:
    body = json.dumps(
        payload,
        ensure_ascii=False
    ).encode("utf-8")

    signature = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Signature-SHA256": f"sha256={signature}"
    }

    for attempt in range(max_retries):
        try:
            response = httpx.post(
                url,
                content=body,
                headers=headers,
                timeout=10.0
            )

            if response.status_code < 500:
                logger.info(
                    "Webhook sent to %s status=%s attempt=%s",
                    url,
                    response.status_code,
                    attempt + 1
                )
                return True

            logger.warning(
                "Webhook returned %s from %s attempt=%s/%s",
                response.status_code,
                url,
                attempt + 1,
                max_retries
            )

        except Exception as error:
            logger.warning(
                "Webhook failed to %s error=%s attempt=%s/%s",
                url,
                error,
                attempt + 1,
                max_retries
            )

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    logger.error(
        "Webhook failed after %s attempts: %s",
        max_retries,
        url
    )

    return False
