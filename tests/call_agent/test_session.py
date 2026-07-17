import os
import json
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
    def __init__(self, finals):
        self._finals = finals
        self._i = 0

    def AcceptWaveform(self, data): return True

    def Result(self):
        t = self._finals[self._i]
        self._i += 1
        return json.dumps({"text": t})

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
    s = _session(["ну и что дальше"])
    s.start()
    actions = s.on_pcm(b"\x00\x00")
    assert all(a.type != "hangup" for a in actions)
    assert s.result().verdict == "undetermined"


def test_greeting_utterance_gets_greeting_reply():
    s = _session(["здравствуйте"])
    s.start()
    actions = s.on_pcm(b"\x00\x00")
    assert all(a.type != "hangup" for a in actions)
    assert actions[0].text in ["Здравствуйте, слушаю вас.", "Добрый день, кто это?",
                               "Здравствуйте, да, я на связи."]


def test_ambiguous_score_without_submitter_falls_through_normally():
    s = _session(["я вам звоню из банка"])   # 25 points, below 70 threshold
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
        "я вам звоню из банка", "повторите пожалуйста код",
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
        "я вам звоню из банка", "что-нибудь ещё",
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
        "я вам звоню из банка", "просто болтаю",
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


def test_tick_resolves_pending_check_without_new_utterance():
    future = concurrent.futures.Future()
    def fake_submit(transcript):
        return future

    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec(["я вам звоню из банка"]))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    s = CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder(), check_submitter=fake_submit)
    s.start()
    s.on_pcm(b"\x00\x00")          # triggers check, returns filler
    future.set_result(True)        # neural net resolves: scam, but caller has gone silent
    actions = s.tick(999999)       # no new speech at all — tick alone must notice

    assert actions[0].type == "speak"
    assert actions[0].text in ["Ой, у меня чайник закипел, я перезвоню.",
                               "Кажется, в дверь звонят, извините, мне пора.",
                               "Ой, второй телефон звонит, мне надо ответить."]
    assert actions[1].type == "hangup"
    assert s.result().verdict == "scam"


def test_periodic_check_fires_after_n_utterances_with_zero_score():
    future = concurrent.futures.Future()
    calls = []
    def fake_submit(transcript):
        calls.append(transcript)
        return future

    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec([
        "привет как дела", "я ваша соседка сверху",
    ]))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    s = CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder(),
                    check_submitter=fake_submit, semantic_check_every_n=2)
    s.start()

    s.on_pcm(b"\x00\x00")              # 1-я реплика: рано, проверки нет
    assert calls == []
    actions = s.on_pcm(b"\x00\x00")    # 2-я реплика: периодическая проверка
    assert len(calls) == 1
    assert "привет как дела" in calls[0]
    assert "я ваша соседка сверху" in calls[0]
    assert actions[0].type == "speak"  # filler, пока ждём нейросеть


def test_periodic_check_counter_resets_after_resolution():
    futures = [concurrent.futures.Future(), concurrent.futures.Future()]
    calls = []
    def fake_submit(transcript):
        calls.append(transcript)
        return futures[len(calls) - 1]

    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec([
        "привет как дела",        # 1: счётчик 1
        "я ваша соседка",         # 2: submit #1, счётчик 0
        "зашла за солью",         # 3: future ещё не готов -> filler
        "и за сахаром",           # 4: резолвим False до этой реплики
        "и за спичками",          # 5: счётчик снова 2 -> submit #2
    ]))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    s = CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder(),
                    check_submitter=fake_submit, semantic_check_every_n=2)
    s.start()
    s.on_pcm(b"\x00\x00")   # 1
    s.on_pcm(b"\x00\x00")   # 2 -> submit #1
    assert len(calls) == 1
    s.on_pcm(b"\x00\x00")   # 3 -> pending, filler
    futures[0].set_result(False)
    s.on_pcm(b"\x00\x00")   # 4 -> resolve(False), счётчик сброшен -> обычный ответ
    assert len(calls) == 1
    s.on_pcm(b"\x00\x00")   # 5 -> накопилось 2 новых реплики -> submit #2
    assert len(calls) == 2


def test_semantic_scam_via_periodic_check_hangs_up():
    future = concurrent.futures.Future()
    def fake_submit(transcript):
        return future

    asr = StreamingASR(cfg.Settings(), recognizer=ScriptRec([
        "здравствуйте это ваш оператор связи",   # 0 баллов правил
        "нужно продлить договор на симкарту",     # 0 баллов -> периодическая проверка
        "вы меня слышите",
    ]))
    det = ScamDetector(load_scenarios(SC))
    dlg = DialogEngine(load_replies(RP))
    s = CallSession("c1", asr, det, dlg, FakeTTS(), NullRecorder(),
                    check_submitter=fake_submit, semantic_check_every_n=2)
    s.start()
    s.on_pcm(b"\x00\x00")
    s.on_pcm(b"\x00\x00")            # submit
    future.set_result(True)          # нейросеть: мошенник
    actions = s.on_pcm(b"\x00\x00")  # resolve -> прощание + hangup
    assert actions[-1].type == "hangup"
    assert s.result().verdict == "scam"
