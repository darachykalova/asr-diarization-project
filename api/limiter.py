import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_DEFAULT_RATE = os.getenv("API_RATE_LIMIT", "60/minute")


def _key_by_api_key_or_ip(request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()[:64]
    return get_remote_address(request)


limiter = Limiter(key_func=_key_by_api_key_or_ip, default_limits=[_DEFAULT_RATE])
