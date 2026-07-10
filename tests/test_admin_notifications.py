"""Тесты polling-уведомлений (T044 — US8)."""
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.auth_users import get_current_user
from api.main import app
from database.models import AdminUser

client = TestClient(app)


def _user(role: str = "moderator") -> AdminUser:
    u = AdminUser()
    u.id = 1; u.login = "mod"; u.role = role
    u.is_blocked = False; u.created_at = datetime(2026, 7, 1)
    return u


_SINCE = "2026-07-01T00:00:00"


def test_updates_returns_items_after_since():
    server_time = datetime(2026, 7, 8, 12, 0, 0)
    items = [
        {"job_id": "abc", "status": "done", "finished_at": datetime(2026, 7, 8, 10, 0, 0)},
        {"job_id": "def", "status": "failed", "finished_at": datetime(2026, 7, 8, 11, 0, 0)},
    ]
    response_data = {"server_time": server_time, "items": items}

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_audio.crud.list_status_updates_since", return_value=response_data):
        resp = client.get(f"/v1/admin/audio/updates?since={_SINCE}")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert "server_time" in data
    assert "items" in data
    assert len(data["items"]) == 2
    assert data["items"][0]["job_id"] == "abc"
    assert data["items"][0]["status"] == "done"


def test_updates_returns_empty_when_no_changes():
    server_time = datetime(2026, 7, 8, 12, 0, 0)
    response_data = {"server_time": server_time, "items": []}

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_audio.crud.list_status_updates_since", return_value=response_data):
        resp = client.get(f"/v1/admin/audio/updates?since={_SINCE}")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_updates_requires_auth():
    resp = client.get(f"/v1/admin/audio/updates?since={_SINCE}")
    assert resp.status_code == 401


def test_updates_requires_since_param():
    app.dependency_overrides[get_current_user] = lambda: _user()
    resp = client.get("/v1/admin/audio/updates")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 422


def test_updates_passes_since_to_crud():
    captured = {}

    def fake(db, since, **kw):
        captured["since"] = since
        return {"server_time": datetime.utcnow(), "items": []}

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_audio.crud.list_status_updates_since", side_effect=fake):
        client.get(f"/v1/admin/audio/updates?since={_SINCE}")
    app.dependency_overrides.pop(get_current_user, None)

    assert captured["since"] is not None
    assert captured["since"].year == 2026


def test_updates_accessible_by_moderator():
    app.dependency_overrides[get_current_user] = lambda: _user(role="moderator")
    with patch("api.routes.admin_audio.crud.list_status_updates_since",
               return_value={"server_time": datetime.utcnow(), "items": []}):
        resp = client.get(f"/v1/admin/audio/updates?since={_SINCE}")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
