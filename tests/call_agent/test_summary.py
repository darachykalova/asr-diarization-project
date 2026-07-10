import call_agent.config as cfg
from call_agent.summary import summarize_transcript


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
    def json(self):
        return self._payload


def test_returns_response_text():
    def fake_post(url, json, timeout):
        return FakeResp(200, {"response": "Звонили из банка, требовали код."})
    out = summarize_transcript("...", cfg.Settings(), http_post=fake_post)
    assert out == "Звонили из банка, требовали код."


def test_returns_none_on_error():
    def boom(url, json, timeout):
        raise RuntimeError("ollama down")
    assert summarize_transcript("...", cfg.Settings(), http_post=boom) is None


def test_returns_none_on_non_200():
    def fake_post(url, json, timeout):
        return FakeResp(500, {})
    assert summarize_transcript("...", cfg.Settings(), http_post=fake_post) is None
