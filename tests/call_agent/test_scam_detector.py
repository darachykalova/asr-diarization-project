import os
from call_agent.scam_detector import load_scenarios, ScamDetector

SCEN_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "call_agent", "scenarios")


def _detector():
    return ScamDetector(load_scenarios(SCEN_DIR))


def test_loads_scenarios():
    scenarios = load_scenarios(SCEN_DIR)
    keys = {s.key for s in scenarios}
    assert keys == {
        "fake_bank", "gas_service", "police",
        "relative_in_trouble", "mobile_operator", "tech_support",
    }


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
    hits = d.feed("продиктуйте код из смс пожалуйста")
    assert any(h.phrase == "код+смс" for h in hits)
    assert d.verdict()[0] == "scam"          # было undetermined при 60 < 70


def test_case_insensitive_and_delta():
    d = _detector()
    delta = sum(h.weight for h in d.feed("СЛУЖБА БЕЗОПАСНОСТИ банка"))
    assert delta == 65  # 40 (служба безопасности) + 25 (банк stem)


def test_phrase_counted_once_per_feed_but_accumulates_across_feeds():
    d = _detector()
    d.feed("служба безопасности")   # 40
    d.feed("служба безопасности")   # +40 = 80 -> scam
    assert d.verdict()[0] == "scam"


def test_leading_score_below_threshold():
    d = _detector()
    d.feed("я вам звоню из банка")            # 25, ниже 70
    key, score, threshold = d.leading_score()
    assert key == "fake_bank"
    assert score == 25
    assert threshold == 70


def test_leading_score_zero_when_no_hits():
    d = _detector()
    key, score, threshold = d.leading_score()
    assert key is None
    assert score == 0
    assert threshold == 0


def test_stems_match_different_word_forms_and_order():
    d = _detector()
    hits = d.feed("мне нужен смс код который пришёл на ваш телефон")
    assert any(h.phrase == "код+смс" for h in hits)


def test_stems_normalize_yo():
    d = _detector()
    # «пришел» без ё должен совпасть так же, как «пришёл»
    hits = d.feed("код который пришел вам на телефон")
    assert any(h.phrase == "код+приш" for h in hits)


def test_iz_banka_scores_low_but_nonzero():
    d = _detector()
    delta = sum(h.weight for h in d.feed("я вам звоню из банка"))
    assert 0 < delta < 70
    assert d.verdict()[0] == "undetermined"


def test_real_call_2026_07_13_regression():
    """Реальные реплики звонка 3a31f00e (Vosk) — раньше все давали 0 баллов."""
    d = _detector()
    d.feed("я бы хотела узнать ваш код который пришёл вам на телефон")
    d.feed("мне нужен смс код который пришёл на ваш телефон")
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "fake_bank"


def test_prodiktovat_infinitive_matches():
    d = _detector()
    hits = d.feed("зайти в смс и продиктовать мне цифры которые у вас в коде")
    assert any(h.phrase == "продикт+код" for h in hits)


def test_innocent_code_mention_stays_undetermined():
    d = _detector()
    d.feed("я тебе код от домофона пришлю вечером")
    assert d.verdict()[0] == "undetermined"


def test_relative_in_trouble_crosses_threshold():
    d = _detector()
    d.feed("мама это я попал в аварию")          # 45 + 45 = 90
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "relative_in_trouble"


def test_innocent_family_call_stays_undetermined():
    d = _detector()
    d.feed("привет мама это я как твои дела")     # 45 < 70
    assert d.verdict()[0] == "undetermined"


def test_mobile_operator_crosses_threshold():
    d = _detector()
    d.feed("ваш номер будет заблокирован завтра")   # 45
    d.feed("нужен перевыпуск сим-карты")             # 45 + 40 = 85
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "mobile_operator"


def test_innocent_simcard_talk_stays_undetermined():
    d = _detector()
    d.feed("я купил новую сим-карту вчера")          # 40 < 70
    assert d.verdict()[0] == "undetermined"


def test_tech_support_crosses_threshold():
    d = _detector()
    d.feed("у вас вирус на компьютере")                       # 40
    d.feed("нужен удалённый доступ к вашему компьютеру")        # 50 -> 90
    verdict, scenario, conf = d.verdict()
    assert verdict == "scam"
    assert scenario == "tech_support"


def test_innocent_software_talk_stays_undetermined():
    d = _detector()
    d.feed("установи мне программу для монтажа видео")     # 40 < 70
    assert d.verdict()[0] == "undetermined"
