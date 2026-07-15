from datetime import datetime
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.auth_users import get_current_user
from api.main import app
from database.models import AdminUser

client = TestClient(app)

def _user(role="moderator"):
    u = AdminUser()
    u.id = 1
    u.login = "m"
    u.role = role
    u.is_blocked = False
    u.created_at = datetime(2026, 7, 1)
    return u

def _page(items):
    return {"items": items, "page": 1, "page_size": 20, "total": len(items), "pages": 1}

def test_list_calls_requires_auth():
    assert client.get("/v1/admin/calls").status_code == 401

def test_list_calls_returns_page():
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_calls.crud.list_calls", return_value=_page([])):
        r = client.get("/v1/admin/calls")
    app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 200
    assert r.json()["total"] == 0

def test_list_calls_passes_verdict_filter():
    captured = {}

    def fake(db, **kw):
        captured.update(kw)
        return _page([])
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_calls.crud.list_calls", side_effect=fake):
        r = client.get("/v1/admin/calls?verdict=scam")
    app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 200
    assert captured.get("verdict") == "scam"

def test_get_call_detail_404():
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_calls.crud.get_call_detail", return_value=None):
        r = client.get("/v1/admin/calls/nope")
    app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 404


def test_regenerate_summary_sets_and_returns():
    app.dependency_overrides[get_current_user] = lambda: _user("super_admin")
    detail = {"call": {"job_id": "job-1"}, "events": []}
    with patch("api.routes.admin_calls.crud.get_call_detail", return_value=detail), \
         patch("api.routes.admin_calls._transcript_text", return_value="расшифровка"), \
         patch("api.routes.admin_calls.summarize_transcript", return_value="Кратко: банк."), \
         patch("api.routes.admin_calls.crud.set_call_summary", return_value=None) as setter:
        r = client.post("/v1/admin/calls/call-1/summary")
    app.dependency_overrides.pop(get_current_user, None)
    assert r.status_code == 200
    assert r.json()["summary"] == "Кратко: банк."
    setter.assert_called_once()
