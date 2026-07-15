import json
import call_agent.config as cfg
from call_agent.streaming_asr import StreamingASR


class FakeRec:
    def __init__(self, script):
        # script: list of (is_final, text)
        self._script = script
        self._i = 0
    def AcceptWaveform(self, data):
        is_final, _ = self._script[self._i]
        return is_final
    def Result(self):
        _, text = self._script[self._i]
        self._i += 1
        return json.dumps({"text": text})
    def PartialResult(self):
        _, text = self._script[self._i]
        self._i += 1
        return json.dumps({"partial": text})
    def FinalResult(self):
        return json.dumps({"text": "хвост"})


def test_partial_then_final():
    rec = FakeRec([(False, "служба"), (True, "служба безопасности")])
    asr = StreamingASR(cfg.Settings(), recognizer=rec)
    assert asr.accept(b"\x00\x00") == {"partial": "служба"}
    assert asr.accept(b"\x00\x00") == {"final": "служба безопасности"}


def test_flush_returns_residual():
    rec = FakeRec([])
    asr = StreamingASR(cfg.Settings(), recognizer=rec)
    assert asr.flush() == "хвост"
