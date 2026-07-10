"""Тесты журнала аудита (T031 — US5). Только super_admin."""
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.auth_users import get_current_user
from api.main import app
from database.models import AdminUser

client = TestClient(app)


def _user(role: str = "super_admin") -> AdminUser:
    u = AdminUser()
    u.id = 1; u.login = "admin"; u.role = role
    u.is_blocked = False; u.created_at = datetime(2026, 7, 1)
    return u


def _log_item(uid: int = 1, job: str = "job-1") -> dict:
    return {
        "id": 1, "user_id": uid, "user_login": "mod",
        "job_id": job, "action": "reveal",
        "created_at": datetime(2026, 7, 8, 10, 0, 0),
    }


def _page(items: list, total: int = 1) -> dict:
    return {"items": items, "page": 1, "page_size": 50, "total": total, "pages": 1}


def test_audit_log_returns_list():
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_audit.crud.list_access_log", return_value=_page([_log_item()])):
        resp = client.get("/v1/admin/audit-log")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["job_id"] == "job-1"
    assert data["items"][0]["user_login"] == "mod"


def test_audit_log_forbidden_for_moderator():
    app.dependency_overrides[get_current_user] = lambda: _user(role="moderator")
    resp = client.get("/v1/admin/audit-log")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 403


def test_audit_log_requires_auth():
    resp = client.get("/v1/admin/audit-log")
    assert resp.status_code == 401


def test_audit_log_passes_user_id_filter():
    captured = {}

    def fake(db, **kwargs):
        captured.update(kwargs)
        return _page([])

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_audit.crud.list_access_log", side_effect=fake):
        resp = client.get("/v1/admin/audit-log?user_id=3")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("user_id") == 3


def test_audit_log_passes_date_filters():
    captured = {}

    def fake(db, **kwargs):
        captured.update(kwargs)
        return _page([])

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_audit.crud.list_access_log", side_effect=fake):
        resp = client.get("/v1/admin/audit-log?date_from=2026-07-01T00:00:00&date_to=2026-07-08T23:59:59")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("date_from") is not None
    assert captured.get("date_to") is not None


def test_audit_log_pagination():
    captured = {}

    def fake(db, **kwargs):
        captured.update(kwargs)
        return {"items": [], "page": 2, "page_size": 10, "total": 30, "pages": 3}

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_audit.crud.list_access_log", side_effect=fake):
        resp = client.get("/v1/admin/audit-log?page=2&page_size=10")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("page") == 2
    assert captured.get("page_size") == 10
