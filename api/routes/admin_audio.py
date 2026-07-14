from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.auth import get_db
from api.auth_users import get_current_user
from api.routes.transcripts import _delete_transcript_everywhere
from database import crud
from api.routes.transcriptions import (
    _save_upload_to_temp_file,
    _upload_temp_file_to_minio,
    _delete_temp_file_safely,
    _create_upload_database_records,
    _resolve_model,
    _get_default_language,
    _get_max_file_size,
)
from services.audio_quality_service import WhisperModelChoice
from services.audio_service import check_audio_file
from schemas.api.transcription_schema import TranscriptionTaskResponse
from tasks.audio_tasks import build_pipeline_chain
from uuid import uuid4

# ВАЖНО: /updates регистрируется ДО /{job_id}, иначе FastAPI
# трактует строку "updates" как значение path-параметра job_id.
router = APIRouter(prefix="/audio", tags=["Admin Audio"])


class AudioListItem(BaseModel):
    job_id: str
    title: str
    uploaded_at: datetime
    duration_sec: Optional[float] = None
    status: str
    speaker_count: int


class AudioListPage(BaseModel):
    items: list[AudioListItem]
    page: int
    page_size: int
    total: int
    pages: int


@router.get("", response_model=AudioListPage)
def list_audio(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None),
    speaker_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, description="Полнотекстовый поиск по транскрипциям"),
    job_id_q: Optional[str] = Query(None, description="Поиск по ID записи (частичное совпадение)"),
    min_speakers: Optional[int] = Query(None, ge=0),
    max_speakers: Optional[int] = Query(None, ge=0),
    speaker_name: Optional[str] = Query(None, description="Поиск по имени спикера (частичное совпадение)"),
    duration_min: Optional[float] = Query(None, ge=0, description="Минимальная длительность, секунды"),
    duration_max: Optional[float] = Query(None, ge=0, description="Максимальная длительность, секунды"),
    sort_by: Optional[str] = Query("uploaded_at", regex="^(uploaded_at|duration|speakers)$"),
    sort_order: Optional[str] = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return crud.list_audio(
        db,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        status=status,
        speaker_id=speaker_id,
        q=q,
        job_id_q=job_id_q,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
        speaker_name=speaker_name,
        duration_min=duration_min,
        duration_max=duration_max,
        sort_by=sort_by or "uploaded_at",
        sort_order=sort_order or "desc",
    )


class AudioStatusUpdate(BaseModel):
    job_id: str
    status: str
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AudioUpdatesResponse(BaseModel):
    server_time: datetime
    items: list[AudioStatusUpdate]


@router.get("/updates", response_model=AudioUpdatesResponse)
def get_updates(
    since: datetime = Query(..., description="ISO-8601 timestamp"),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return crud.list_status_updates_since(db, since)


@router.get("/{job_id}", response_model=AudioListItem)
def get_audio_item(
    job_id: str,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    item = crud.get_audio_item(db, job_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    return item


@router.delete("/{job_id}")
def delete_audio(
    job_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = _delete_transcript_everywhere(job_id)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="Запись не найдена")

    crud.create_access_log(
        db, user_id=current_user.id, job_id=result["job_id"], action="delete"
    )

    return {
        "message": f"Аудиозапись {result['job_id']} удалена",
        "job_id": result["job_id"],
        "audio_key": result["audio_key"],
        "minio_deleted": result["minio_deleted"],
        "qdrant_deleted": result["qdrant_deleted"],
        "postgres_deleted": result["postgres_deleted"],
    }


@router.post("/upload", response_model=TranscriptionTaskResponse, status_code=202)
async def admin_upload(
    file: UploadFile = File(...),
    whisper_model: Optional[WhisperModelChoice] = None,
    language: str = "auto",
    _user=Depends(get_current_user),
):
    try:
        resolved_model = _resolve_model(whisper_model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job_id = str(uuid4())
    original_filename = file.filename or "audio.bin"
    object_key = f"jobs/{job_id}/{original_filename}"
    temp_path = None

    try:
        temp_path, _ = await _save_upload_to_temp_file(file, max_size=_get_max_file_size())

        try:
            await run_in_threadpool(
                check_audio_file, temp_path, original_filename, file.content_type
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        await run_in_threadpool(
            _upload_temp_file_to_minio, temp_path, object_key, file.content_type
        )

        if language == "auto":
            lang = _get_default_language()
        else:
            lang = language

        # max_speakers из настроек платформы
        from database.session import SessionLocal as _SL
        _db = _SL()
        try:
            _spk_val = crud.get_setting_value(_db, "max_speakers")
            platform_max_speakers = int(_spk_val) if _spk_val and _spk_val.strip().isdigit() else None
        finally:
            _db.close()

        params = {
            "language": lang,
            "whisper_model": resolved_model.value if resolved_model else None,
        }
        await run_in_threadpool(
            _create_upload_database_records,
            job_id, object_key, original_filename, None, params,
        )

        chain = build_pipeline_chain(
            job_id=job_id,
            input_key=object_key,
            language=lang,
            whisper_model=resolved_model.value if resolved_model else None,
            max_speakers=platform_max_speakers,
        )
        chain.delay()

        return {"job_id": job_id, "status": "queued", "input_audio": object_key}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if temp_path:
            await run_in_threadpool(_delete_temp_file_safely, temp_path)
