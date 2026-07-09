import os
from call_agent.scam_detector import load_scenarios, ScamDetector

SCEN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "call_agent", "scenarios")


def _detector():
    return ScamDetector(load_scenarios(SCEN_DIR))


def test_loads_three_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {"fake_bank", "gas_service", "police"}


def test_clean_call_is_undetermined():
    d = _detector()
    d.feed("привет это мама как дела")
    verdict, scenario, conf = d.verdict()
    assert verdict == "undetermined"
    assert scenario is None
    assert conf == 0


def test_bank_scam_crosses_threshold():
    d = _detector()
    d.feed("здравствуйте это служба безопасности банка")   # 40
    d.feed("ваша карта заблокирована")                       # +30 = 70
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "fake_bank"
    assert conf == 100


def test_single_strong_phrase_enough():
    d = _detector()
    hits = d.feed("продиктуйте код из смс пожалуйста")        # 60, below 70
    assert any(h.phrase == "продиктуйте код" for h in hits)
    assert d.verdict()[0] == "undetermined"


def test_case_insensitive_and_delta():
    d = _detector()
    delta = sum(h.weight for h in d.feed("СЛУЖБА БЕЗОПАСНОСТИ банка"))
    assert delta == 40


def test_phrase_counted_once_per_feed_but_accumulates_across_feeds():
    d = _detector()
    d.feed("служба безопасности")   # 40
    d.feed("служба безопасности")   # +40 = 80 -> scam
    assert d.verdict()[0] == "scam"
