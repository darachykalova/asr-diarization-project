import os
from unittest.mock import MagicMock, patch


def _make_mock_client(existing_size: int | None = None):
    client = MagicMock()
    collections = MagicMock()

    if existing_size is None:
        collections.collections = []
    else:
        col = MagicMock()
        col.name = "speaker_voices"
        collections.collections = [col]
        col_info = MagicMock()
        col_info.config.params.vectors.size = existing_size
        client.get_collection.return_value = col_info

    client.get_collections.return_value = collections
    return client


def test_vector_size_is_192():
    from services.speaker_identification_service import SpeakerIdentificationService
    assert SpeakerIdentificationService.VECTOR_SIZE == 192


def test_match_threshold_default_is_0_80(monkeypatch):
    monkeypatch.delenv("SPEAKER_MATCH_THRESHOLD", raising=False)
    import importlib
    import services.speaker_identification_service as mod
    importlib.reload(mod)
    assert mod.SpeakerIdentificationService.MATCH_THRESHOLD == 0.80


def test_match_threshold_reads_from_env(monkeypatch):
    monkeypatch.setenv("SPEAKER_MATCH_THRESHOLD", "0.75")
    import importlib
    import services.speaker_identification_service as mod
    importlib.reload(mod)
    assert mod.SpeakerIdentificationService.MATCH_THRESHOLD == 0.75


def test_ensure_collection_creates_when_missing():
    client = _make_mock_client(existing_size=None)
    with patch("services.speaker_identification_service.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        SpeakerIdentificationService()
    client.create_collection.assert_called_once()
    client.delete_collection.assert_not_called()


def test_ensure_collection_recreates_on_size_mismatch():
    client = _make_mock_client(existing_size=512)
    with patch("services.speaker_identification_service.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        SpeakerIdentificationService()
    client.delete_collection.assert_called_once_with("speaker_voices")
    client.create_collection.assert_called_once()


def test_ensure_collection_skips_when_size_matches():
    client = _make_mock_client(existing_size=192)
    with patch("services.speaker_identification_service.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        SpeakerIdentificationService()
    client.delete_collection.assert_not_called()
    client.create_collection.assert_not_called()


def test_find_speaker_returns_none_when_no_points():
    client = _make_mock_client(existing_size=192)
    result = MagicMock()
    result.points = []
    client.query_points.return_value = result
    with patch("services.speaker_identification_service.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        service = SpeakerIdentificationService()
        speaker_id, score = service.find_speaker([0.0] * 192)
    assert speaker_id is None
    assert score is None


def test_find_speaker_returns_id_when_score_above_threshold():
    client = _make_mock_client(existing_size=192)
    point = MagicMock()
    point.score = 0.92
    point.payload = {"speaker_id": 42}
    result = MagicMock()
    result.points = [point]
    client.query_points.return_value = result
    with patch("services.speaker_identification_service.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        service = SpeakerIdentificationService()
        speaker_id, score = service.find_speaker([0.0] * 192)
    assert speaker_id == 42
    assert score == 0.92


def test_find_speaker_returns_none_when_score_below_threshold():
    client = _make_mock_client(existing_size=192)
    point = MagicMock()
    point.score = 0.65
    point.payload = {"speaker_id": 42}
    result = MagicMock()
    result.points = [point]
    client.query_points.return_value = result
    with patch("services.speaker_identification_service.QdrantClient", return_value=client):
        from services.speaker_identification_service import SpeakerIdentificationService
        service = SpeakerIdentificationService()
        speaker_id, score = service.find_speaker([0.0] * 192)
    assert speaker_id is None
    assert score == 0.65
