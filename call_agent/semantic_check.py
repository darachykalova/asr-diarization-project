"""Real-time semantic scam check via local Ollama. Never raises — fails safe to False."""
from __future__ import annotations

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
            timeout=15,
        )
        if resp.status_code != 200:
            return False
        answer = (resp.json().get("response") or "").strip().lower()
        return answer.startswith("да")
    except Exception:
        return False
