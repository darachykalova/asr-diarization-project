import os, json
import concurrent.futures
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


def test_ambiguous_score_without_submitter_falls_through_normally():
    s = _session(["продиктуйте код из смс"])   # 60 points, below 70 threshold
    s.start()
    actions = s.on_pcm(b"\x00\x00")
    assert all(a.type != "hangup" for a in actions)
    assert s.result().verdict == "undetermined"


def test_ambiguous_score_triggers_background_check_and_stalls():
    future = concurrent.futures.Future()
    calls = []
    def fake_submit(transcript):
        calls.append(transcript)
        return future

    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec([
        "продиктуйте код из смс", "повторите пожалуйста код",
    ]))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    s = CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder(), check_submitter=fake_submit)
    s.start()

    actions1 = s.on_pcm(b"\x00\x00")
    assert len(calls) == 1
    assert actions1[0].type == "speak"

    actions2 = s.on_pcm(b"\x00\x00")   # still pending -> another filler, no second submit
    assert len(calls) == 1
    assert actions2[0].type == "speak"


def test_semantic_check_confirms_scam_then_hangs_up():
    future = concurrent.futures.Future()
    def fake_submit(transcript):
        return future

    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec([
        "продиктуйте код из смс", "что-нибудь ещё",
    ]))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    s = CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder(), check_submitter=fake_submit)
    s.start()
    s.on_pcm(b"\x00\x00")            # triggers check, returns filler
    future.set_result(True)          # neural net resolves: scam
    actions = s.on_pcm(b"\x00\x00")  # next turn: resolve

    assert actions[0].type == "speak"
    assert actions[0].text in ["Ой, у меня чайник закипел, я перезвоню.",
                               "Кажется, в дверь звонят, извините, мне пора.",
                               "Ой, второй телефон звонит, мне надо ответить."]
    assert actions[1].type == "hangup"
    result = s.result()
    assert result.verdict == "scam"
    assert result.scenario == "fake_bank"
    assert result.ended_reason == "detected_scam"


def test_semantic_check_clears_and_resumes_normal_conversation():
    future = concurrent.futures.Future()
    def fake_submit(transcript):
        return future

    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec([
        "продиктуйте код из смс", "просто болтаю",
    ]))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    s = CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder(), check_submitter=fake_submit)
    s.start()
    s.on_pcm(b"\x00\x00")            # triggers check, returns filler
    future.set_result(False)         # neural net resolves: not scam
    actions = s.on_pcm(b"\x00\x00")  # next turn: resumes normally

    assert all(a.type != "hangup" for a in actions)
    assert actions[0].text in ["Ага… и что?", "Так, а мне что делать?",
                               "Ой, а куда нажать-то?", "Подождите, я не поняла."]
    assert s.result().verdict == "undetermined"
