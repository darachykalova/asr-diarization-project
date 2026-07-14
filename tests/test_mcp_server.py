"""Проверка регистрации MCP-инструментов (без обращения к БД)."""
import asyncio

import pytest

pytest.importorskip("mcp")  # в CI пакета mcp нет — тест скипается


def test_all_tools_registered():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert {
        "search_transcripts", "get_transcript",
        "list_recent_calls", "get_call", "call_stats",
    } <= names


def test_tools_have_descriptions():
    from mcp_server.server import mcp
    tools = asyncio.run(mcp.list_tools())
    for t in tools:
        assert t.description, f"у инструмента {t.name} нет описания"
