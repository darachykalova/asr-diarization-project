"""
Тесты DELETE /v1/admin/audio/{job_id}.

Гарантии:
- Удаление доступно модератору и super_admin
- 404, если запись не найдена; аудит при 404 не пишется
- При успехе пишется audit log с action="delete"
- Требуется авторизация
"""
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.auth_users import get_current_user
from api.main import app
from database.models import AdminUser

client = TestClient(app)


def _make_user(role: str = "moderator") -> AdminUser:
    user = AdminUser()
    user.id = 3
    user.login = "testmod"
    user.role = role
    user.is_blocked = False
    user.created_at = datetime(2026, 7, 1)
    return user


def _deleted_result(job_id: str = "job-1") -> dict:
    return {
        "deleted": True,
        "job_id": job_id,
        "audio_key": f"jobs/{job_id}/audio.wav",
        "minio_deleted": True,
        "qdrant_deleted": True,
        "postgres_deleted": True,
    }


def test_delete_audio_returns_summary():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio._delete_transcript_everywhere", return_value=_deleted_result("job-1")), \
         patch("api.routes.admin_audio.crud.create_access_log"):
        resp = client.delete("/v1/admin/audio/job-1")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "job-1"
    assert data["postgres_deleted"] is True
    assert data["minio_deleted"] is True
    assert data["qdrant_deleted"] is True


def test_delete_audio_accessible_by_moderator():
    app.dependency_overrides[get_current_user] = lambda: _make_user(role="moderator")
    with patch("api.routes.admin_audio._delete_transcript_everywhere", return_value=_deleted_result()), \
         patch("api.routes.admin_audio.crud.create_access_log"):
        resp = client.delete("/v1/admin/audio/job-1")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200


def test_delete_audio_accessible_by_super_admin():
    app.dependency_overrides[get_current_user] = lambda: _make_user(role="super_admin")
    with patch("api.routes.admin_audio._delete_transcript_everywhere", return_value=_deleted_result()), \
         patch("api.routes.admin_audio.crud.create_access_log"):
        resp = client.delete("/v1/admin/audio/job-1")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200


def test_delete_audio_requires_auth():
    resp = client.delete("/v1/admin/audio/job-1")
    assert resp.status_code == 401


def test_delete_audio_404_when_not_found():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch(
        "api.routes.admin_audio._delete_transcript_everywhere",
        return_value={"deleted": False, "reason": "not_found"},
    ), patch("api.routes.admin_audio.crud.create_access_log") as mock_log:
        resp = client.delete("/v1/admin/audio/no-such-job")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 404
    mock_log.assert_not_called()


def test_delete_audio_writes_audit_log():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio._delete_transcript_everywhere", return_value=_deleted_result("job-1")), \
         patch("api.routes.admin_audio.crud.create_access_log") as mock_log:
        client.delete("/v1/admin/audio/job-1")
    app.dependency_overrides.pop(get_current_user, None)

    mock_log.assert_called_once()
    _, kwargs = mock_log.call_args
    assert kwargs.get("user_id") == 3
    assert kwargs.get("job_id") == "job-1"
    assert kwargs.get("action") == "delete"
