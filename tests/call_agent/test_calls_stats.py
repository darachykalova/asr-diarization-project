"""Тест статистики звонков (нужен запущенный postgres)."""
from datetime import datetime, timedelta

import pytest

from database import crud
from database.models import Call
from database.session import SessionLocal

pytestmark = pytest.mark.requires_db


def test_call_verdict_stats_counts_by_verdict():
    db = SessionLocal()
    ids = ["call-stats-scam", "call-stats-ok"]
    try:
        crud.create_call(db, ids[0], "browser", datetime.utcnow())
        crud.finalize_call(db, ids[0], datetime.utcnow(), 10.0, "scam",
                           "fake_bank", 90, "detected_scam", None, "k1")
        crud.create_call(db, ids[1], "browser", datetime.utcnow())
        crud.finalize_call(db, ids[1], datetime.utcnow(), 20.0, "undetermined",
                           None, 0, "caller_hangup", None, "k2")

        stats = crud.call_verdict_stats(db, date_from=datetime.utcnow() - timedelta(days=1))
        assert stats["total"] >= 2
        assert stats["by_verdict"].get("scam", 0) >= 1
        assert stats["by_verdict"].get("undetermined", 0) >= 1
        assert stats["avg_duration_sec"] is None or stats["avg_duration_sec"] > 0
    finally:
        db.query(Call).filter(Call.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        db.close()
