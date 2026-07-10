"""
Тесты для GET /v1/admin/audio и GET /v1/admin/audio/{job_id} (T018 — US2).

Паттерн: переопределяем get_current_user через dependency_overrides,
CRUD-функции мокаем через patch.
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
    user.id = 1
    user.login = "testmod"
    user.role = role
    user.is_blocked = False
    user.created_at = datetime(2026, 7, 1)
    return user


def _item(job_id: str = "job-1", status: str = "done", speaker_count: int = 2) -> dict:
    return {
        "job_id": job_id,
        "title": "test.mp3",
        "uploaded_at": datetime(2026, 7, 1, 12, 0, 0),
        "duration_sec": 120.5,
        "status": status,
        "speaker_count": speaker_count,
    }


def _page(items: list, total: int = 1) -> dict:
    return {
        "items": items,
        "page": 1,
        "page_size": 20,
        "total": total,
        "pages": 1,
    }


# ---------------------------------------------------------------------------
# GET /v1/admin/audio
# ---------------------------------------------------------------------------

def test_list_audio_returns_paginated():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.list_audio", return_value=_page([_item()])):
        resp = client.get("/v1/admin/audio")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["items"][0]["job_id"] == "job-1"
    assert data["items"][0]["speaker_count"] == 2


def test_list_audio_requires_auth():
    resp = client.get("/v1/admin/audio")
    assert resp.status_code == 401


def test_list_audio_accessible_by_moderator():
    app.dependency_overrides[get_current_user] = lambda: _make_user(role="moderator")
    with patch("api.routes.admin_audio.crud.list_audio", return_value=_page([])):
        resp = client.get("/v1/admin/audio")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 200


def test_list_audio_passes_status_filter():
    captured = {}

    def fake_list_audio(db, **kwargs):
        captured.update(kwargs)
        return _page([_item(status="done")])

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.list_audio", side_effect=fake_list_audio):
        resp = client.get("/v1/admin/audio?status=done")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("status") == "done"


def test_list_audio_passes_speaker_id_filter():
    captured = {}

    def fake_list_audio(db, **kwargs):
        captured.update(kwargs)
        return _page([])

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.list_audio", side_effect=fake_list_audio):
        resp = client.get("/v1/admin/audio?speaker_id=42")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("speaker_id") == 42


def test_list_audio_passes_date_filters():
    captured = {}

    def fake_list_audio(db, **kwargs):
        captured.update(kwargs)
        return _page([])

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.list_audio", side_effect=fake_list_audio):
        resp = client.get(
            "/v1/admin/audio?date_from=2026-07-01T00:00:00&date_to=2026-07-08T23:59:59"
        )
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("date_from") is not None
    assert captured.get("date_to") is not None


def test_list_audio_passes_fts_query():
    captured = {}

    def fake_list_audio(db, **kwargs):
        captured.update(kwargs)
        return _page([_item()])

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.list_audio", side_effect=fake_list_audio):
        resp = client.get("/v1/admin/audio?q=привет")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("q") == "привет"


def test_list_audio_combined_filters():
    captured = {}

    def fake_list_audio(db, **kwargs):
        captured.update(kwargs)
        return _page([])

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.list_audio", side_effect=fake_list_audio):
        resp = client.get("/v1/admin/audio?status=done&speaker_id=1&q=тест")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("status") == "done"
    assert captured.get("speaker_id") == 1
    assert captured.get("q") == "тест"


def test_list_audio_pagination_params():
    captured = {}

    def fake_list_audio(db, **kwargs):
        captured.update(kwargs)
        return {"items": [], "page": 2, "page_size": 10, "total": 25, "pages": 3}

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.list_audio", side_effect=fake_list_audio):
        resp = client.get("/v1/admin/audio?page=2&page_size=10")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("page") == 2
    assert captured.get("page_size") == 10


# ---------------------------------------------------------------------------
# GET /v1/admin/audio/{job_id}
# ---------------------------------------------------------------------------

def test_get_audio_item_returns_metadata():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.get_audio_item", return_value=_item("job-42")):
        resp = client.get("/v1/admin/audio/job-42")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == "job-42"
    assert data["duration_sec"] == 120.5
    assert data["status"] == "done"


def test_get_audio_item_returns_404_when_not_found():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.get_audio_item", return_value=None):
        resp = client.get("/v1/admin/audio/nonexistent")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 404


def test_get_audio_item_requires_auth():
    resp = client.get("/v1/admin/audio/some-job")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Новые фильтры: speaker_name, duration_min, duration_max, job_id_q
# ---------------------------------------------------------------------------

def test_list_audio_passes_speaker_name_filter():
    captured = {}

    def fake_list_audio(db, **kwargs):
        captured.update(kwargs)
        return _page([])

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.list_audio", side_effect=fake_list_audio):
        resp = client.get("/v1/admin/audio?speaker_name=Иван")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("speaker_name") == "Иван"


def test_list_audio_passes_duration_filters():
    captured = {}

    def fake_list_audio(db, **kwargs):
        captured.update(kwargs)
        return _page([])

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.list_audio", side_effect=fake_list_audio):
        resp = client.get("/v1/admin/audio?duration_min=60&duration_max=300")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("duration_min") == 60.0
    assert captured.get("duration_max") == 300.0


def test_list_audio_duration_min_negative_returns_422():
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    resp = client.get("/v1/admin/audio?duration_min=-1")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 422


def test_list_audio_passes_job_id_q_filter():
    captured = {}

    def fake_list_audio(db, **kwargs):
        captured.update(kwargs)
        return _page([])

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("api.routes.admin_audio.crud.list_audio", side_effect=fake_list_audio):
        resp = client.get("/v1/admin/audio?job_id_q=abc-123")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    assert captured.get("job_id_q") == "abc-123"
