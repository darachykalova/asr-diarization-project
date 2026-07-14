import os
import random
from call_agent.dialog_engine import DialogEngine, load_replies

REPLIES = os.path.join(os.path.dirname(__file__), "..", "..", "call_agent", "persona", "replies.yaml")


def _engine():
    return DialogEngine(load_replies(REPLIES), rng=random.Random(0))


def test_greeting_from_pool():
    e = _engine()
    assert e.greeting() in ["Алло?", "Да, слушаю вас."]


def test_scam_verdict_triggers_hangup_with_no_line():
    e = _engine()
    reply = e.on_caller_utterance("продиктуйте код из смс", verdict="scam")
    assert reply.hang_up is True
    assert reply.kind == "hangup"
    assert reply.text == ""


def test_undetermined_keeps_talking():
    e = _engine()
    reply = e.on_caller_utterance("а что случилось", verdict="undetermined")
    assert reply.hang_up is False
    assert reply.kind == "talk"
    assert reply.text in ["Ага… и что?", "Так, а мне что делать?",
                          "Ой, а куда нажать-то?", "Подождите, я не поняла."]


def test_filler_from_pool():
    e = _engine()
    assert e.filler() in ["Сейчас-сейчас, минуточку…", "А? Повторите, пожалуйста.",
                          "Ой, подождите, очки найду.", "Кхм… кхм…",
                          "Ой, погодите, ручку возьму, чтобы записать.",
                          "Так, так… минуточку, соображу."]


def test_before_hangup_line():
    e = _engine()
    assert e.before_hangup_line() in ["Ой, у меня чайник закипел, я перезвоню.",
                                      "Кажется, в дверь звонят, извините, мне пора.",
                                      "Ой, второй телефон звонит, мне надо ответить."]


def test_take_message_line():
    e = _engine()
    assert e.take_message_line() == "Хозяина сейчас нет дома, он перезвонит. Что передать?"


def test_filler_never_repeats_immediately():
    e = _engine()
    prev = e.filler()
    for _ in range(50):
        cur = e.filler()
        assert cur != prev, "одна и та же stalling-фраза дважды подряд"
        prev = cur


def test_keep_talking_never_repeats_immediately():
    e = _engine()
    prev = e.on_caller_utterance("что", verdict="undetermined").text
    for _ in range(50):
        cur = e.on_caller_utterance("что", verdict="undetermined").text
        assert cur != prev
        prev = cur


def test_single_option_key_still_repeats():
    # take_message содержит один вариант — повторы допустимы и не должны падать
    e = _engine()
    line = "Хозяина сейчас нет дома, он перезвонит. Что передать?"
    assert e.take_message_line() == line
    assert e.take_message_line() == line
