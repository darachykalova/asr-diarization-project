import importlib


def test_defaults(monkeypatch):
    for var in ["VOSK_MODEL_PATH", "SILERO_SPEAKER", "NOT_SCAM_TIMEOUT_SEC",
                "N8N_CALL_ALERT_WEBHOOK_URL"]:
        monkeypatch.delenv(var, raising=False)
    import call_agent.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.silero_speaker == "baya"
    assert s.not_scam_timeout_sec == 180
    assert s.scenarios_dir.endswith("scenarios")
    assert s.n8n_call_alert_webhook_url is None


def test_env_override(monkeypatch):
    monkeypatch.setenv("SILERO_SPEAKER", "xenia")
    monkeypatch.setenv("NOT_SCAM_TIMEOUT_SEC", "90")
    import call_agent.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.silero_speaker == "xenia"
    assert s.not_scam_timeout_sec == 90


def test_call_alert_webhook_env_override(monkeypatch):
    monkeypatch.setenv("N8N_CALL_ALERT_WEBHOOK_URL", "http://n8n:5678/webhook/call-alert")
    import call_agent.config as cfg
    importlib.reload(cfg)
    s = cfg.get_settings()
    assert s.n8n_call_alert_webhook_url == "http://n8n:5678/webhook/call-alert"


def test_semantic_check_every_n_default(monkeypatch):
    monkeypatch.delenv("SEMANTIC_CHECK_EVERY_N_UTTERANCES", raising=False)
    import call_agent.config as cfg
    importlib.reload(cfg)
    assert cfg.get_settings().semantic_check_every_n == 2


def test_semantic_check_every_n_from_env(monkeypatch):
    monkeypatch.setenv("SEMANTIC_CHECK_EVERY_N_UTTERANCES", "5")
    import call_agent.config as cfg
    importlib.reload(cfg)
    assert cfg.get_settings().semantic_check_every_n == 5
