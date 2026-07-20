"""Real-time semantic scam check via local Ollama. Never raises — fails safe to False."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_PROMPT = (
    "Ты определяешь, похож ли телефонный разговор на мошенничество. "
    "Вот разговор до сих пор:\n\n"
)


def check_scam_semantically(transcript: str, settings, http_post=None) -> bool:
    if http_post is None:
        import httpx
        http_post = httpx.post
    try:
        resp = http_post(
            f"{settings.ollama_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": _PROMPT + transcript
                    + "\n\nЭто мошенничество? Ответь одним словом: да или нет.",
                "stream": False,
            },
            # Была 15s: холодная загрузка модели после простоя (>keep_alive) занимает
            # ~90-100с — таймаут срабатывал раньше ответа, и проверка молча уходила
            # в False на каждом первом звонке. Вызов асинхронный (ThreadPoolExecutor
            # в session.py), так что более долгий таймаут не блокирует сам звонок.
            timeout=120,
        )
        if resp.status_code != 200:
            logger.warning(
                "semantic check: Ollama returned HTTP %s (model=%s, url=%s)",
                resp.status_code, settings.ollama_model, settings.ollama_url)
            return False
        answer = (resp.json().get("response") or "").strip().lower()
        return answer.startswith("да")
    except Exception as exc:
        logger.warning(
            "semantic check failed (model=%s, url=%s): %s",
            settings.ollama_model, settings.ollama_url, exc)
        return False
