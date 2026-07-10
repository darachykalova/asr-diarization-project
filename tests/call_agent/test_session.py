import os, json
import call_agent.config as cfg
from call_agent.scam_detector import load_scenarios, ScamDetector
from call_agent.dialog_engine import DialogEngine, load_replies
from call_agent.streaming_asr import StreamingASR
from call_agent.session import CallSession, CallState

SC = os.path.join(os.path.dirname(__file__), "..", "..", "call_agent", "scenarios")
RP = os.path.join(os.path.dirname(__file__), "..", "..", "call_agent", "persona", "replies.yaml")


class FakeTTS:
    def synthesize(self, text): return f"/tmp/{abs(hash(text))}.wav"


class ScriptRec:
    def __init__(self, finals): self._finals = finals; self._i = 0
    def AcceptWaveform(self, data): return True
    def Result(self):
        t = self._finals[self._i]; self._i += 1; return json.dumps({"text": t})
    def PartialResult(self): return json.dumps({"partial": ""})
    def FinalResult(self): return json.dumps({"text": ""})


class NullRecorder:
    def write_caller(self, b): pass
    def write_agent(self, b): pass


def _session(finals):
    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec(finals))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    return CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder())


def test_greeting_first():
    s = _session([])
    action = s.start()
    assert action.type == "speak"
    assert action.wav_path is not None


def test_scam_flow_hangs_up():
    s = _session(["служба безопасности банка", "карта заблокирована"])
    s.start()
    s.on_pcm(b"\x00\x00")                      # utterance 1: +40
    actions = s.on_pcm(b"\x00\x00")            # utterance 2: +30 -> 70 scam
    assert any(a.type == "hangup" for a in actions)
    assert s.result().verdict == "scam"
    assert s.result().scenario == "fake_bank"


def test_clean_call_keeps_talking():
    s = _session(["привет как дела"])
    s.start()
    actions = s.on_pcm(b"\x00\x00")
    assert all(a.type != "hangup" for a in actions)
    assert s.result().verdict == "undetermined"
