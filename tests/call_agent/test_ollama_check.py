"""Тесты стартовой проверки доступности Ollama-модели (warning, не crash)."""
import logging

import httpx

from call_agent.main import _check_ollama_ready


class FakeResp:
    def __init__(self, payload):
        self._payload = payload
    def json(self):
        return self._payload


def test_warns_when_model_missing(monkeypatch, caplog):
    monkeypatch.setattr(httpx, "get", lambda url, timeout: FakeResp({"models": []}))
    with caplog.at_level(logging.WARNING, logger="call_agent.main"):
        _check_ollama_ready()
    assert any("ollama pull" in r.message for r in caplog.records)


def test_silent_when_model_present(monkeypatch, caplog):
    monkeypatch.setattr(httpx, "get", lambda url, timeout: FakeResp(
        {"models": [{"name": "qwen2.5:3b"}]}))
    with caplog.at_level(logging.WARNING, logger="call_agent.main"):
        _check_ollama_ready()
    assert caplog.records == []


def test_warns_but_does_not_raise_when_ollama_down(monkeypatch, caplog):
    def boom(url, timeout):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(httpx, "get", boom)
    with caplog.at_level(logging.WARNING, logger="call_agent.main"):
        _check_ollama_ready()   # не должно бросить
    assert any("not reachable" in r.message.lower() for r in caplog.records)
