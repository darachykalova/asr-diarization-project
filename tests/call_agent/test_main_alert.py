from unittest.mock import patch

from call_agent.main import _build_transcript_text, _send_call_alert


def test_send_call_alert_posts_to_webhook_when_configured():
    with patch("services.webhook_service.send_webhook") as mock_send:
        _send_call_alert("http://n8n:5678/webhook/call-alert", "call-123", "scam")
    mock_send.assert_called_once_with(
        url="http://n8n:5678/webhook/call-alert",
        payload={"call_id": "call-123", "verdict": "scam", "summary": None},
    )


def test_send_call_alert_includes_summary_when_given():
    with patch("services.webhook_service.send_webhook") as mock_send:
        _send_call_alert("http://n8n:5678/webhook/call-alert", "call-123", "scam",
                         summary="Звонили из банка, требовали код.")
    mock_send.assert_called_once_with(
        url="http://n8n:5678/webhook/call-alert",
        payload={"call_id": "call-123", "verdict": "scam",
                "summary": "Звонили из банка, требовали код."},
    )


def test_build_transcript_text_labels_speakers_in_order():
    events = [
        (0.0, "agent", "Здравствуйте", 0),
        (1.5, "caller", "Это банк, ваша карта заблокирована", 40),
        (3.0, "agent", "Назовите код из смс?", 0),
    ]
    text = _build_transcript_text(events)
    assert text == (
        "Агент: Здравствуйте\n"
        "Звонящий: Это банк, ваша карта заблокирована\n"
        "Агент: Назовите код из смс?"
    )


def test_send_call_alert_skips_when_url_not_configured():
    with patch("services.webhook_service.send_webhook") as mock_send:
        _send_call_alert(None, "call-123", "scam")
    mock_send.assert_not_called()


def test_send_call_alert_swallows_webhook_errors():
    with patch("services.webhook_service.send_webhook", side_effect=RuntimeError("boom")):
        _send_call_alert("http://n8n:5678/webhook/call-alert", "call-123", "undetermined")
        # must not raise — the assertion is simply that this line is reached
