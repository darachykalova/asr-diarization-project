"""Post-call summary via local Ollama. Never raises — returns None on failure."""
from __future__ import annotations

_PROMPT = (
    "Ты помощник, который кратко пересказывает телефонный разговор на русском языке. "
    "Опиши в 2-3 предложениях, о чём был звонок, кто звонил и что просили. "
    "Вот расшифровка разговора:\n\n"
)


def summarize_transcript(full_text: str, settings, http_post=None) -> str | None:
    if http_post is None:
        import httpx
        http_post = httpx.post
    try:
        resp = http_post(
            f"{settings.ollama_url}/api/generate",
            json={"model": settings.ollama_model, "prompt": _PROMPT + full_text, "stream": False},
            timeout=240,
        )
        if resp.status_code != 200:
            return None
        return resp.json().get("response")
    except Exception:
        return None
