from datetime import datetime, timedelta

from database.database import Base
from database.models import Call, CallEvent
from database import crud


def test_call_models_registered():
    assert "calls" in Base.metadata.tables
    assert "call_events" in Base.metadata.tables


def test_create_and_finalize_call():
    from database.session import SessionLocal
    db = SessionLocal()
    try:
        cid = "call-test-1"
        crud.create_call(db, cid, source="browser", started_at=datetime.utcnow())
        crud.add_call_event(db, cid, at=1.0, speaker="caller", text="служба безопасности", scam_delta=40)
        crud.add_call_event(db, cid, at=2.0, speaker="agent", text="алло", scam_delta=0)
        crud.finalize_call(db, cid, ended_at=datetime.utcnow(), duration_sec=12.0,
                           verdict="scam", scenario="fake_bank", confidence=100,
                           ended_reason="detected_scam", job_id=None, audio_key="calls/x.wav")
        detail = crud.get_call_detail(db, cid)
        assert detail["call"]["verdict"] == "scam"
        assert detail["call"]["confidence"] == 100
        assert len(detail["events"]) == 2
        assert detail["events"][0]["speaker"] == "caller"
    finally:
        db.query(CallEvent).filter_by(call_id="call-test-1").delete()
        db.query(Call).filter_by(id="call-test-1").delete()
        db.commit()
        db.close()


def test_list_calls_filters_by_verdict():
    from database.session import SessionLocal
    db = SessionLocal()
    try:
        crud.create_call(db, "call-scam", "browser", datetime.utcnow())
        crud.finalize_call(db, "call-scam", datetime.utcnow(), 5.0, "scam",
                           "fake_bank", 90, "detected_scam", None, "k")
        page = crud.list_calls(db, verdict="scam")
        assert any(i["call_id"] == "call-scam" for i in page["items"])
        assert all(i["verdict"] == "scam" for i in page["items"])
    finally:
        db.query(Call).filter_by(id="call-scam").delete()
        db.commit()
        db.close()
