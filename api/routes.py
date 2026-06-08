import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File

from tasks import process_audio_task
from services.qdrant_service import QdrantService
from services.text_embedding_service import TextEmbeddingService

router = APIRouter()


@router.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "ASR Diarization Service"
    }


@router.post("/transcriptions")
def create_transcription(audio_path: str):
    job_id = f"job_{uuid4().hex}"

    task = process_audio_task.delay(
        input_audio=audio_path,
        job_id=job_id
    )

    return {
        "job_id": job_id,
        "celery_task_id": task.id,
        "status": "queued"
    }


@router.post("/transcriptions/upload")
async def upload_transcription(file: UploadFile = File(...)):
    job_id = f"job_{uuid4().hex}"

    upload_dir = Path("data/input/jobs") / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    input_audio_path = upload_dir / file.filename

    with open(input_audio_path, "wb") as output_file:
        content = await file.read()
        output_file.write(content)

    task = process_audio_task.delay(
        input_audio=str(input_audio_path),
        job_id=job_id
    )

    return {
        "job_id": job_id,
        "celery_task_id": task.id,
        "status": "queued",
        "input_audio": str(input_audio_path)
    }


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job_status_path = (
        Path("data/output/jobs")
        / job_id
        / "job_status.json"
    )

    if not job_status_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Job not found: {job_id}"
        )

    with open(
        job_status_path,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


@router.get("/transcripts/{job_id}")
def get_transcript(job_id: str):
    transcript_path = (
        Path("data/output/jobs")
        / job_id
        / "transcript.json"
    )

    if not transcript_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found for job: {job_id}"
        )

    with open(
        transcript_path,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


@router.get("/qdrant/health")
def qdrant_health():
    qdrant_service = QdrantService()

    return {
        "qdrant_available": qdrant_service.health_check()
    }


@router.get("/qdrant/collections")
def qdrant_collections():
    qdrant_service = QdrantService()

    try:
        collections = qdrant_service.client.get_collections()

        return {
            "collections": [
                collection.name
                for collection in collections.collections
            ]
        }

    except Exception as error:
        return {
            "collections": [],
            "error": str(error)
        }


@router.get("/qdrant/segments/{job_id}")
def qdrant_segments(job_id: str):
    qdrant_service = QdrantService()

    segments = qdrant_service.get_segments_by_job(
        job_id
    )

    return {
        "job_id": job_id,
        "count": len(segments),
        "segments": segments
    }


@router.get("/qdrant/search")
def qdrant_search(
    query: str,
    job_id: str | None = None
):
    qdrant_service = QdrantService()

    results = qdrant_service.search_text(
        query=query,
        job_id=job_id
    )

    return {
        "query": query,
        "job_id": job_id,
        "count": len(results),
        "results": results
    }


@router.get("/qdrant/semantic-search")
def qdrant_semantic_search(
    query: str,
    job_id: str | None = None,
    limit: int = 5
):
    qdrant_service = QdrantService()

    results = qdrant_service.semantic_search(
        query=query,
        job_id=job_id,
        limit=limit
    )

    return {
        "query": query,
        "job_id": job_id,
        "limit": limit,
        "count": len(results),
        "results": results
    }


@router.get("/embeddings/text")
def create_text_embedding(text: str):
    service = TextEmbeddingService()

    vector = service.embed_text(text)

    return {
        "text": text,
        "dimension": len(vector),
        "vector_preview": vector[:20]
    }