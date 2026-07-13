import call_agent.config as cfg
from call_agent.semantic_check import check_scam_semantically


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
    def json(self):
        return self._payload


def test_returns_true_when_answer_is_da():
    def fake_post(url, json, timeout):
        return FakeResp(200, {"response": "Да, это похоже на мошенничество."})
    assert check_scam_semantically("...", cfg.Settings(), http_post=fake_post) is True


def test_returns_false_when_answer_is_net():
    def fake_post(url, json, timeout):
        return FakeResp(200, {"response": "Нет, обычный разговор."})
    assert check_scam_semantically("...", cfg.Settings(), http_post=fake_post) is False


def test_returns_false_on_error():
    def boom(url, json, timeout):
        raise RuntimeError("ollama down")
    assert check_scam_semantically("...", cfg.Settings(), http_post=boom) is False


def test_returns_false_on_non_200():
    def fake_post(url, json, timeout):
        return FakeResp(500, {})
    assert check_scam_semantically("...", cfg.Settings(), http_post=fake_post) is False
