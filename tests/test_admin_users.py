"""
Тесты управления пользователями (T027 — US4).
GET/POST /v1/admin/users, PATCH /v1/admin/users/{id} — только super_admin.
"""
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth_users import get_current_user
from api.main import app
from database.models import AdminUser

client = TestClient(app)


def _user(role: str = "super_admin", uid: int = 1) -> AdminUser:
    u = AdminUser()
    u.id = uid
    u.login = "admin"
    u.role = role
    u.is_blocked = False
    u.created_at = datetime(2026, 7, 1)
    return u


def _db_user(uid: int = 2, login: str = "mod", role: str = "moderator") -> AdminUser:
    u = AdminUser()
    u.id = uid
    u.login = login
    u.password_hash = "x"
    u.role = role
    u.is_blocked = False
    u.created_at = datetime(2026, 7, 1)
    return u


# ---------------------------------------------------------------------------
# GET /v1/admin/users
# ---------------------------------------------------------------------------

def test_list_users_returns_list():
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_users.crud.list_admin_users", return_value=[_db_user()]):
        resp = client.get("/v1/admin/users")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["login"] == "mod"


def test_list_users_forbidden_for_moderator():
    app.dependency_overrides[get_current_user] = lambda: _user(role="moderator")
    resp = client.get("/v1/admin/users")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 403


def test_list_users_requires_auth():
    resp = client.get("/v1/admin/users")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /v1/admin/users
# ---------------------------------------------------------------------------

def test_create_user_success():
    app.dependency_overrides[get_current_user] = lambda: _user()
    new_user = _db_user(uid=3, login="newmod", role="moderator")
    with patch("api.routes.admin_users.crud.get_admin_user_by_login", return_value=None), \
         patch("api.routes.admin_users.crud.create_admin_user", return_value=new_user):
        resp = client.post("/v1/admin/users", json={"login": "newmod", "password": "secret123"})
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 201
    assert resp.json()["login"] == "newmod"


def test_create_user_conflict_when_login_exists():
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_users.crud.get_admin_user_by_login", return_value=_db_user()):
        resp = client.post("/v1/admin/users", json={"login": "mod", "password": "password123"})
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 409


def test_create_user_forbidden_for_moderator():
    app.dependency_overrides[get_current_user] = lambda: _user(role="moderator")
    resp = client.post("/v1/admin/users", json={"login": "x", "password": "password123"})
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /v1/admin/users/{id} — смена роли
# ---------------------------------------------------------------------------

def test_patch_role_success():
    updated = _db_user(role="super_admin")
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_users.crud.update_admin_user_role", return_value=updated), \
         patch("api.routes.admin_users.crud.get_admin_user_by_id", return_value=updated):
        resp = client.patch("/v1/admin/users/2", json={"role": "super_admin"})
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert resp.json()["role"] == "super_admin"


def test_patch_role_409_last_super_admin():
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch(
        "api.routes.admin_users.crud.update_admin_user_role",
        side_effect=ValueError("Нельзя убрать роль у последнего активного супер-админа"),
    ):
        resp = client.patch("/v1/admin/users/1", json={"role": "moderator"})
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# PATCH /v1/admin/users/{id} — блокировка
# ---------------------------------------------------------------------------

def test_patch_blocked_success():
    blocked_user = _db_user()
    blocked_user.is_blocked = True
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_users.crud.set_admin_user_blocked", return_value=blocked_user), \
         patch("api.routes.admin_users.crud.get_admin_user_by_id", return_value=blocked_user):
        resp = client.patch("/v1/admin/users/2", json={"is_blocked": True})
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert resp.json()["is_blocked"] is True


def test_patch_block_409_last_super_admin():
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch(
        "api.routes.admin_users.crud.set_admin_user_blocked",
        side_effect=ValueError("Нельзя заблокировать последнего активного супер-админа"),
    ):
        resp = client.patch("/v1/admin/users/1", json={"is_blocked": True})
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 409


def test_patch_user_404():
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_users.crud.update_admin_user_role", return_value=None):
        resp = client.patch("/v1/admin/users/999", json={"role": "moderator"})
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 404


def test_patch_user_forbidden_for_moderator():
    app.dependency_overrides[get_current_user] = lambda: _user(role="moderator")
    resp = client.patch("/v1/admin/users/2", json={"is_blocked": True})
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 403
