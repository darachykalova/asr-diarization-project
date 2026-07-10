"""
Tests for /v1/admin/auth/login and /v1/admin/auth/me (T013 — US1).

Pattern: patch CRUD calls at the module where they are used; override the
get_current_user dependency directly for /me tests so no real DB or JWT
verification is needed.
"""
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.auth_users import create_token, get_current_user, hash_password
from api.main import app
from database.models import AdminUser

client = TestClient(app)


def _make_user(role: str = "super_admin", is_blocked: bool = False) -> AdminUser:
    user = AdminUser()
    user.id = 1
    user.login = "testadmin"
    user.role = role
    user.is_blocked = is_blocked
    user.password_hash = hash_password("correct_password")
    user.created_at = datetime(2026, 7, 8, 0, 0, 0)
    return user


# ---------------------------------------------------------------------------
# POST /v1/admin/auth/login
# ---------------------------------------------------------------------------

def test_login_success():
    user = _make_user()
    with patch("api.routes.admin_auth.get_admin_user_by_login", return_value=user):
        resp = client.post(
            "/v1/admin/auth/login",
            json={"login": "testadmin", "password": "correct_password"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "super_admin"


def test_login_wrong_password():
    user = _make_user()
    with patch("api.routes.admin_auth.get_admin_user_by_login", return_value=user):
        resp = client.post(
            "/v1/admin/auth/login",
            json={"login": "testadmin", "password": "wrong_password"},
        )
    assert resp.status_code == 401


def test_login_user_not_found():
    with patch("api.routes.admin_auth.get_admin_user_by_login", return_value=None):
        resp = client.post(
            "/v1/admin/auth/login",
            json={"login": "nobody", "password": "any_password"},
        )
    assert resp.status_code == 401


def test_login_blocked_user():
    user = _make_user(is_blocked=True)
    with patch("api.routes.admin_auth.get_admin_user_by_login", return_value=user):
        resp = client.post(
            "/v1/admin/auth/login",
            json={"login": "testadmin", "password": "correct_password"},
        )
    assert resp.status_code == 401


def test_login_missing_fields():
    resp = client.post("/v1/admin/auth/login", json={"login": "only_login"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /v1/admin/auth/me
# ---------------------------------------------------------------------------

def test_me_returns_profile_for_super_admin():
    user = _make_user(role="super_admin")
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = client.get("/v1/admin/auth/me")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    data = resp.json()
    assert data["login"] == "testadmin"
    assert data["role"] == "super_admin"
    assert data["is_blocked"] is False


def test_me_returns_profile_for_moderator():
    user = _make_user(role="moderator")
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        resp = client.get("/v1/admin/auth/me")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200
    assert resp.json()["role"] == "moderator"


def test_me_without_token_returns_401():
    resp = client.get("/v1/admin/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token_returns_401():
    resp = client.get(
        "/v1/admin/auth/me",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# require_role guard: unit-test the inner _check function directly
# ---------------------------------------------------------------------------

def test_require_role_blocks_moderator():
    from fastapi import HTTPException
    from api.auth_users import require_role

    check = require_role("super_admin")
    moderator = _make_user(role="moderator")
    with pytest.raises(HTTPException) as exc_info:
        check(user=moderator)
    assert exc_info.value.status_code == 403


def test_require_role_allows_super_admin():
    from api.auth_users import require_role

    check = require_role("super_admin")
    super_admin = _make_user(role="super_admin")
    result = check(user=super_admin)
    assert result is super_admin
