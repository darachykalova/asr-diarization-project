from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.auth import verify_api_key
from api.main import app

client = TestClient(app)


def _override_auth():
    mock_key = MagicMock()
    mock_key.scopes = "admin"
    return mock_key


def test_health_check():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Audio Intelligence API"
    }


def test_get_missing_transcript_returns_404():
    app.dependency_overrides[verify_api_key] = _override_auth

    with patch("api.routes.transcripts.crud.get_transcript_by_job_id", return_value=None):
        response = client.get("/v1/transcripts/non-existing-job-id")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Transcript not found for job: non-existing-job-id"
    )


def test_search_requires_query():
    app.dependency_overrides[verify_api_key] = _override_auth
    response = client.get("/v1/search")
    app.dependency_overrides.clear()

    assert response.status_code == 422


def test_search_rejects_invalid_limit():
    app.dependency_overrides[verify_api_key] = _override_auth
    response = client.get("/v1/search", params={"q": "test", "limit": 0})
    app.dependency_overrides.clear()

    assert response.status_code == 422


def test_upload_transcription_requires_file():
    app.dependency_overrides[verify_api_key] = _override_auth
    response = client.post("/v1/transcriptions/upload")
    app.dependency_overrides.clear()

    assert response.status_code == 422


def test_openapi_schema_is_available():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    assert "paths" in schema
    assert "/" in schema["paths"]
    assert "/v1/transcriptions/upload" in schema["paths"]
    assert "/v1/jobs/{job_id}" in schema["paths"]
    assert "/v1/transcripts/{job_id}" in schema["paths"]
    assert "/v1/search" in schema["paths"]


def test_project_readme_exists():
    assert Path("README.md").exists()
