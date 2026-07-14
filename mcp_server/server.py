"""MCP-сервер проекта: поиск по транскриптам и статистика звонков.

Запускается на хост-машине (не в Docker) через stdio — Claude Code
поднимает процесс сам согласно .mcp.json в корне репозитория.
БД доступна через проброшенный порт Postgres (localhost:5432);
DATABASE_URL по умолчанию из database/database.py подходит как есть.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# сервер запускается как скрипт из корня репо — добавляем корень в sys.path,
# чтобы работали импорты database.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from database import crud  # noqa: E402
from database.session import SessionLocal  # noqa: E402

mcp = FastMCP(
    "asr-diarization",
    host="0.0.0.0",  # в docker-сети слушаем все интерфейсы; наружу порт открывает compose
    port=int(os.getenv("MCP_HTTP_PORT", "8200")),
)


def _clean(value):
    """datetime -> isoformat рекурсивно, чтобы ответ был JSON-сериализуем."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


@mcp.tool()
def search_transcripts(query: str, limit: int = 10) -> list[dict]:
    """Полнотекстовый поиск по всем транскриптам аудиозаписей.

    Возвращает job_id, язык, длительность и фрагмент текста (snippet)
    с совпадением. Для полного текста используй get_transcript.
    """
    return crud.search_transcripts_fulltext(query, limit)


@mcp.tool()
def get_transcript(job_id: str) -> dict:
    """Полный транскрипт по job_id: текст целиком и сегменты со спикерами
    и таймкодами (start/end в секундах)."""
    result = crud.get_transcript_by_job_id(job_id)
    if result is None:
        return {"error": f"Транскрипт с job_id={job_id} не найден"}
    return _clean(result)


@mcp.tool()
def list_recent_calls(verdict: str | None = None, days: int = 7,
                      limit: int = 20) -> dict:
    """Последние звонки анти-скам агента за N дней.

    verdict — фильтр по вердикту (например 'scam' или 'undetermined'),
    None = все. Возвращает call_id, время начала, длительность, вердикт,
    сценарий и уверенность.
    """
    db = SessionLocal()
    try:
        date_from = datetime.utcnow() - timedelta(days=days)
        return _clean(crud.list_calls(db, page=1, page_size=limit,
                                      verdict=verdict, date_from=date_from))
    finally:
        db.close()


@mcp.tool()
def get_call(call_id: str) -> dict:
    """Детали одного звонка: вердикт, сценарий, сводка (summary) и полная
    расшифровка реплик с пометками, какие фразы повышали скам-балл."""
    db = SessionLocal()
    try:
        detail = crud.get_call_detail(db, call_id)
        if detail is None:
            return {"error": f"Звонок с call_id={call_id} не найден"}
        return _clean(detail)
    finally:
        db.close()


@mcp.tool()
def call_stats(days: int = 7) -> dict:
    """Статистика звонков анти-скам агента за N дней: сколько всего,
    разбивка по вердиктам, средняя длительность в секундах."""
    db = SessionLocal()
    try:
        date_from = datetime.utcnow() - timedelta(days=days)
        return crud.call_verdict_stats(db, date_from=date_from)
    finally:
        db.close()


def _build_http_app():
    """Streamable-HTTP приложение с Bearer-авторизацией.

    Без MCP_AUTH_TOKEN отказывается собираться: HTTP-режим открывает
    транскрипты по сети, пускать туда без токена нельзя.
    """
    token = os.getenv("MCP_AUTH_TOKEN", "")
    if not token:
        raise SystemExit(
            "MCP_AUTH_TOKEN не задан — HTTP-режим без авторизации запрещён. "
            "Добавь MCP_AUTH_TOKEN в .env"
        )

    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class BearerAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.headers.get("authorization") != f"Bearer {token}":
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            return await call_next(request)

    # FastMCP кэширует session manager на первом вызове streamable_http_app()
    # и он одноразовый (RuntimeError при повторном run() того же инстанса).
    # В проде _build_http_app() вызывается один раз за процесс — не важно;
    # но чтобы функция была идемпотентна (повторные вызовы в одном процессе,
    # как в тестах), сбрасываем кэш перед каждой сборкой.
    mcp._session_manager = None
    app = mcp.streamable_http_app()  # эндпоинт протокола: POST /mcp
    app.add_middleware(BearerAuthMiddleware)
    return app


if __name__ == "__main__":
    if os.getenv("MCP_TRANSPORT", "stdio") == "http":
        import uvicorn
        uvicorn.run(_build_http_app(), host="0.0.0.0",
                    port=int(os.getenv("MCP_HTTP_PORT", "8200")))
    else:
        mcp.run()  # stdio — локальный режим для Claude Code
