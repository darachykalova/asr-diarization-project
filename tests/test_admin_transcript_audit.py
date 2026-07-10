"""
Тесты POST /v1/admin/audio/{job_id}/transcript:reveal (T023 — US3).

Гарантии:
- Аудит пишется при каждом успешном reveal
- Текст транскрипции НЕ попадает в audit log (конституция VI)
- 404 при отсутствии транскрипции; аудит при 404 НЕ пишется
- Reveal доступен модератору и super_admin
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.auth_users import get_current_user
from api.main import app
from database.models import AdminUser

client = TestClient(app)


def _make_user(role: str = "moderator") -> AdminUser:
    user = AdminUser()
    user.id = 7
    user.login = "testmod"
    user.role = role
    user.is_blocked = False
    user.created_at = datetime(2026, 7, 1)
    return user


def _reveal_data(job_id: str = "job-1") -> dict:
    return {
        "job_id": job_id,
        "language": "ru",
        "speakers": [
            {"speaker": "SPEAKER_00", "speaker_id": 1, "display_name": "Иван"},
        ],
        "segments": [
            {"start": 0.0, "end": 5.2, "speaker": "SPEAKER_00", "text": "Привет"},
            {"start": 5.5, "end": 10.0, "speaker": "SPEAKER_00", "text": "как дела"},
        ],
    }


# ---------------------------------------------------------------------------
# Базовые ответы
# ---------------------------------------------------------------------------

def test_reveal_returns_segments():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_transcript.crud.get_transcript_reveal_data", return_value=_reveal_data()), \
         patch("api.routes.admin_transcript.crud.create_access_log"):
        resp = client.post("/v1/admin/audio/job-1/transcript:reveal")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "job-1"
    assert data["language"] == "ru"
    assert len(data["segments"]) == 2
    assert data["segments"][0]["text"] == "Привет"
    assert data["speakers"][0]["speaker"] == "SPEAKER_00"


def test_reveal_accessible_by_moderator():
    app.dependency_overrides[get_current_user] = lambda: _make_user(role="moderator")
    with patch("api.routes.admin_transcript.crud.get_transcript_reveal_data", return_value=_reveal_data()), \
         patch("api.routes.admin_transcript.crud.create_access_log"):
        resp = client.post("/v1/admin/audio/job-1/transcript:reveal")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200


def test_reveal_accessible_by_super_admin():
    app.dependency_overrides[get_current_user] = lambda: _make_user(role="super_admin")
    with patch("api.routes.admin_transcript.crud.get_transcript_reveal_data", return_value=_reveal_data()), \
         patch("api.routes.admin_transcript.crud.create_access_log"):
        resp = client.post("/v1/admin/audio/job-1/transcript:reveal")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200


def test_reveal_requires_auth():
    resp = client.post("/v1/admin/audio/job-1/transcript:reveal")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 404 при отсутствии транскрипции
# ---------------------------------------------------------------------------

def test_reveal_404_when_no_transcript():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_transcript.crud.get_transcript_reveal_data", return_value=None), \
         patch("api.routes.admin_transcript.crud.create_access_log") as mock_log:
        resp = client.post("/v1/admin/audio/no-such-job/transcript:reveal")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 404
    mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# Аудит пишется при каждом reveal (конституция)
# ---------------------------------------------------------------------------

def test_reveal_writes_audit_log():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_transcript.crud.get_transcript_reveal_data", return_value=_reveal_data()), \
         patch("api.routes.admin_transcript.crud.create_access_log") as mock_log:
        client.post("/v1/admin/audio/job-1/transcript:reveal")
    app.dependency_overrides.pop(get_current_user, None)

    mock_log.assert_called_once()


def test_reveal_audit_log_contains_user_id_and_job_id():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_transcript.crud.get_transcript_reveal_data", return_value=_reveal_data()), \
         patch("api.routes.admin_transcript.crud.create_access_log") as mock_log:
        client.post("/v1/admin/audio/job-1/transcript:reveal")
    app.dependency_overrides.pop(get_current_user, None)

    _, kwargs = mock_log.call_args
    assert kwargs.get("user_id") == 7   # id из _make_user
    assert kwargs.get("job_id") == "job-1"
    assert kwargs.get("action") == "reveal"


# ---------------------------------------------------------------------------
# Конституция принцип VI: текст не пишется в аудит
# ---------------------------------------------------------------------------

def test_reveal_audit_log_has_no_transcript_text():
    """Ни один аргумент create_access_log не должен содержать текст сегментов."""
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    captured: dict = {}

    def capture_log(db, **kwargs):
        captured.update(kwargs)

    with patch("api.routes.admin_transcript.crud.get_transcript_reveal_data", return_value=_reveal_data()), \
         patch("api.routes.admin_transcript.crud.create_access_log", side_effect=capture_log):
        client.post("/v1/admin/audio/job-1/transcript:reveal")
    app.dependency_overrides.pop(get_current_user, None)

    # Значения переданных аргументов не должны содержать текст сегментов
    serialized = str(captured)
    assert "Привет" not in serialized
    assert "как дела" not in serialized
    assert "text" not in captured
    assert "segments" not in captured
