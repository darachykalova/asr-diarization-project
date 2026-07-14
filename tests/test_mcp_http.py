"""HTTP-режим MCP-сервера: авторизация по Bearer-токену."""
import pytest

pytest.importorskip("mcp")  # в CI пакета mcp нет — тест скипается

from starlette.testclient import TestClient  # noqa: E402


def test_http_app_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "secret-token")
    from mcp_server import server
    with TestClient(server._build_http_app()) as client:
        r = client.post("/mcp", json={})
        assert r.status_code == 401


def test_http_app_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "secret-token")
    from mcp_server import server
    with TestClient(server._build_http_app()) as client:
        r = client.post("/mcp", json={},
                        headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 401


def test_http_app_accepts_valid_token(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_TOKEN", "secret-token")
    from mcp_server import server
    with TestClient(server._build_http_app()) as client:
        r = client.post("/mcp", json={},
                        headers={"Authorization": "Bearer secret-token"})
        # дальше срабатывает MCP-протокол (может вернуть 400/406 на пустое
        # тело) — важно лишь, что авторизация пройдена, т.е. не 401
        assert r.status_code != 401


def test_http_app_refuses_to_build_without_token(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    from mcp_server import server
    with pytest.raises(SystemExit):
        server._build_http_app()
