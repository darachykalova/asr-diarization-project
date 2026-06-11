from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_health_check():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Audio Intelligence API"
    }


def test_get_missing_transcript_returns_404():
    response = client.get("/transcripts/non-existing-job-id")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Transcript not found for job: non-existing-job-id"
    )


def test_calls_search_requires_query():
    response = client.get("/calls/search")

    assert response.status_code == 422


def test_calls_search_rejects_invalid_limit():
    response = client.get(
        "/calls/search",
        params={
            "query": "test",
            "limit": 0
        }
    )

    assert response.status_code == 422


def test_upload_transcription_requires_file():
    response = client.post("/transcriptions/upload")

    assert response.status_code == 422


def test_openapi_schema_is_available():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    assert "paths" in schema
    assert "/" in schema["paths"]
    assert "/calls/search" in schema["paths"]
    assert "/transcriptions/upload" in schema["paths"]
    assert "/jobs/{job_id}" in schema["paths"]
    assert "/transcripts/{job_id}" in schema["paths"]


def test_project_readme_exists():
    assert Path("README.md").exists()