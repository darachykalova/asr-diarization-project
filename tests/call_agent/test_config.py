import importlib


def test_defaults(monkeypatch):
    for var in ["VOSK_MODEL_PATH", "SILERO_SPEAKER", "NOT_SCAM_TIMEOUT_SEC"]:
        monkeypatch.delenv(var, raising=False)
    import call_agent.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.silero_speaker == "baya"
    assert s.not_scam_timeout_sec == 180
    assert s.scenarios_dir.endswith("scenarios")


def test_env_override(monkeypatch):
    monkeypatch.setenv("SILERO_SPEAKER", "xenia")
    monkeypatch.setenv("NOT_SCAM_TIMEOUT_SEC", "90")
    import call_agent.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.silero_speaker == "xenia"
    assert s.not_scam_timeout_sec == 90
