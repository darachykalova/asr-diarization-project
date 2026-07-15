"""Тесты аналитики (T035 — US6)."""
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.auth_users import get_current_user
from api.main import app
from database.models import AdminUser

client = TestClient(app)


def _user(role: str = "moderator") -> AdminUser:
    u = AdminUser()
    u.id = 1
    u.login = "mod"
    u.role = role
    u.is_blocked = False
    u.created_at = datetime(2026, 7, 1)
    return u


# ---------------------------------------------------------------------------
# /analytics/summary
# ---------------------------------------------------------------------------

def test_summary_returns_counts():
    summary = {"total_audio": 42, "total_transcribed": 38, "by_status": {"done": 38, "failed": 4}}
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_analytics.crud.analytics_summary", return_value=summary):
        resp = client.get("/v1/admin/analytics/summary")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_audio"] == 42
    assert data["total_transcribed"] == 38
    assert data["by_status"]["done"] == 38


def test_summary_requires_auth():
    resp = client.get("/v1/admin/analytics/summary")
    assert resp.status_code == 401


def test_summary_accessible_by_moderator():
    app.dependency_overrides[get_current_user] = lambda: _user(role="moderator")
    with patch("api.routes.admin_analytics.crud.analytics_summary",
               return_value={"total_audio": 0, "total_transcribed": 0, "by_status": {}}):
        resp = client.get("/v1/admin/analytics/summary")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /analytics/frequent-words
# ---------------------------------------------------------------------------

def test_frequent_words_returns_list():
    words = [{"word": "привет", "count": 100}, {"word": "мир", "count": 50}]
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_analytics.crud.frequent_words", return_value=words):
        resp = client.get("/v1/admin/analytics/frequent-words")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["word"] == "привет"
    assert data[0]["count"] == 100


def test_frequent_words_passes_limit():
    captured = {}

    def fake(db, **kwargs):
        captured.update(kwargs)
        return []

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_analytics.crud.frequent_words", side_effect=fake):
        resp = client.get("/v1/admin/analytics/frequent-words?limit=10")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("limit") == 10


def test_frequent_words_requires_auth():
    resp = client.get("/v1/admin/analytics/frequent-words")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /analytics/frequent-speakers
# ---------------------------------------------------------------------------

def test_frequent_speakers_returns_list():
    speakers = [{"speaker_id": 1, "name": "Иван", "count": 30}]
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_analytics.crud.frequent_speakers", return_value=speakers):
        resp = client.get("/v1/admin/analytics/frequent-speakers")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["name"] == "Иван"
    assert data[0]["count"] == 30


def test_frequent_speakers_passes_limit():
    captured = {}

    def fake(db, **kwargs):
        captured.update(kwargs)
        return []

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_analytics.crud.frequent_speakers", side_effect=fake):
        client.get("/v1/admin/analytics/frequent-speakers?limit=5")
    app.dependency_overrides.pop(get_current_user, None)
    assert captured.get("limit") == 5


# ---------------------------------------------------------------------------
# /analytics/uploads-over-time
# ---------------------------------------------------------------------------

def test_uploads_over_time_returns_buckets():
    buckets = [
        {"bucket": datetime(2026, 7, 1), "count": 10},
        {"bucket": datetime(2026, 7, 2), "count": 15},
    ]
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_analytics.crud.uploads_over_time", return_value=buckets):
        resp = client.get("/v1/admin/analytics/uploads-over-time")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["count"] == 10


def test_uploads_over_time_passes_bucket_param():
    captured = {}

    def fake(db, **kwargs):
        captured.update(kwargs)
        return []

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_analytics.crud.uploads_over_time", side_effect=fake):
        resp = client.get("/v1/admin/analytics/uploads-over-time?bucket=hour")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("bucket") == "hour"


def test_uploads_over_time_rejects_invalid_bucket():
    app.dependency_overrides[get_current_user] = lambda: _user()
    resp = client.get("/v1/admin/analytics/uploads-over-time?bucket=week")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 422
