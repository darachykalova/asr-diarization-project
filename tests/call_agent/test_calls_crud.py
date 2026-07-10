from database.database import Base
from database.models import Call, CallEvent


def test_call_models_registered():
    assert "calls" in Base.metadata.tables
    assert "call_events" in Base.metadata.tables
