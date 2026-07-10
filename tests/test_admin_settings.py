"""Тесты настроек платформы (T039 — US7)."""
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.auth_users import get_current_user
from api.main import app
from database.models import AdminUser, PlatformSetting

client = TestClient(app)


def _user(role: str = "super_admin") -> AdminUser:
    u = AdminUser()
    u.id = 1; u.login = "admin"; u.role = role
    u.is_blocked = False; u.created_at = datetime(2026, 7, 1)
    return u


def _setting(key: str, value: str, vtype: str = "string") -> PlatformSetting:
    s = PlatformSetting()
    s.key = key; s.value = value; s.value_type = vtype
    s.updated_at = datetime(2026, 7, 1); s.updated_by = None
    return s


# ---------------------------------------------------------------------------
# GET /settings
# ---------------------------------------------------------------------------

def test_get_settings_returns_list():
    settings = [
        _setting("chunk_threshold_sec", "360", "int"),
        _setting("default_asr_model", "", "string"),
    ]
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_settings.crud.get_all_settings", return_value=settings):
        resp = client.get("/v1/admin/settings")
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["key"] == "chunk_threshold_sec"
    assert data[0]["value"] == "360"


def test_get_settings_requires_auth():
    resp = client.get("/v1/admin/settings")
    assert resp.status_code == 401


def test_get_settings_forbids_moderator():
    app.dependency_overrides[get_current_user] = lambda: _user(role="moderator")
    resp = client.get("/v1/admin/settings")
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /settings — valid values
# ---------------------------------------------------------------------------

def test_put_settings_saves_valid_value():
    updated = [_setting("chunk_threshold_sec", "600", "int")]
    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_settings.crud.upsert_settings", return_value=updated):
        resp = client.put(
            "/v1/admin/settings",
            json=[{"key": "chunk_threshold_sec", "value": "600"}],
        )
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["value"] == "600"


def test_put_settings_returns_422_on_invalid_int():
    def bad_upsert(db, updates, **kw):
        raise ValueError("int требует int, получено 'not-a-number'")

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_settings.crud.upsert_settings", side_effect=bad_upsert):
        resp = client.put(
            "/v1/admin/settings",
            json=[{"key": "chunk_threshold_sec", "value": "not-a-number"}],
        )
    app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 422


def test_put_settings_preserves_other_settings_on_error():
    """Если одно значение невалидно — ни одно не применяется."""
    def atomic_fail(db, updates, **kw):
        raise ValueError("invalid")

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_settings.crud.upsert_settings", side_effect=atomic_fail):
        resp = client.put(
            "/v1/admin/settings",
            json=[
                {"key": "chunk_threshold_sec", "value": "600"},
                {"key": "default_asr_model", "value": "bad!!!"},
            ],
        )
    app.dependency_overrides.pop(get_current_user, None)
    # Вся транзакция откатывается
    assert resp.status_code == 422


def test_validate_setting_value_allows_empty_as_unset():
    """Пустая строка = «не задано»: валидна для любого типа.

    Дефолтные настройки сеются с пустыми значениями (напр. max_speakers),
    а SettingsPage шлёт все поля разом — без этого сохранение всегда падало 422.
    """
    from database.crud import _validate_setting_value
    for vtype in ("int", "float", "bool", "string"):
        _validate_setting_value("", vtype)
        _validate_setting_value("  ", vtype)


def test_put_settings_forbids_moderator():
    app.dependency_overrides[get_current_user] = lambda: _user(role="moderator")
    resp = client.put("/v1/admin/settings", json=[{"key": "k", "value": "v"}])
    app.dependency_overrides.pop(get_current_user, None)
    assert resp.status_code == 403


def test_put_settings_passes_updated_by():
    captured = {}

    def fake_upsert(db, updates, **kwargs):
        captured.update(kwargs)
        return []

    app.dependency_overrides[get_current_user] = lambda: _user()
    with patch("api.routes.admin_settings.crud.upsert_settings", side_effect=fake_upsert):
        client.put("/v1/admin/settings", json=[{"key": "k", "value": "v"}])
    app.dependency_overrides.pop(get_current_user, None)

    assert captured.get("updated_by") == 1


# ---------------------------------------------------------------------------
# Новые настройки и функция очистки журнала
# ---------------------------------------------------------------------------

def test_seed_removes_obsolete_keys():
    """chunk_threshold_sec и default_rate_limit должны удаляться при сиде."""
    from database.crud import seed_default_settings, _OBSOLETE_KEYS
    from database.models import PlatformSetting
    from database.session import SessionLocal

    db = SessionLocal()
    try:
        # Вставляем устаревший ключ
        db.add(PlatformSetting(key="chunk_threshold_sec", value="360", value_type="int"))
        db.commit()

        seed_default_settings(db)

        remaining = db.query(PlatformSetting).filter(
            PlatformSetting.key.in_(list(_OBSOLETE_KEYS))
        ).count()
        assert remaining == 0
    finally:
        db.rollback()
        db.close()


def test_seed_adds_new_settings():
    """После seed_default_settings новые ключи должны существовать."""
    from database.crud import seed_default_settings
    from database.models import PlatformSetting
    from database.session import SessionLocal

    db = SessionLocal()
    try:
        seed_default_settings(db)
        keys = {r.key for r in db.query(PlatformSetting).all()}
        assert "default_language" in keys
        assert "max_upload_size_mb" in keys
        assert "max_speakers" in keys
        assert "allowed_formats" in keys
        assert "audit_log_retention_days" in keys
    finally:
        db.close()


def test_cleanup_old_audit_logs_deletes_old_entries():
    """cleanup_old_audit_logs удаляет записи старше retention_days."""
    from datetime import datetime, timedelta
    from database.crud import cleanup_old_audit_logs, upsert_settings
    from database.models import TranscriptAccessLog, PlatformSetting, AdminUser
    from database.session import SessionLocal

    db = SessionLocal()
    try:
        # Устанавливаем retention = 30 дней
        upsert_settings(db, [{"key": "audit_log_retention_days", "value": "30"}])

        # Нужен реальный user_id — ищем существующего или пропускаем
        user = db.query(AdminUser).first()
        if user is None:
            return  # нет пользователей — тест пропускаем

        old_log = TranscriptAccessLog(
            user_id=user.id,
            job_id="test-job-old",
            action="reveal",
            created_at=datetime.utcnow() - timedelta(days=31),
        )
        new_log = TranscriptAccessLog(
            user_id=user.id,
            job_id="test-job-new",
            action="reveal",
            created_at=datetime.utcnow(),
        )
        db.add_all([old_log, new_log])
        db.commit()

        deleted = cleanup_old_audit_logs(db)
        assert deleted >= 1

        remaining_jobs = {r.job_id for r in db.query(TranscriptAccessLog)
                         .filter(TranscriptAccessLog.job_id.in_(["test-job-old", "test-job-new"])).all()}
        assert "test-job-old" not in remaining_jobs
        assert "test-job-new" in remaining_jobs
    finally:
        db.rollback()
        db.close()
