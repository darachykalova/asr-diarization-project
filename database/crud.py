from datetime import datetime, timedelta
from math import ceil

from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from database.models import (
    AdminUser,
    Call,
    CallEvent,
    Job,
    Occurrence,
    PlatformSetting,
    Recording,
    Speaker,
    Transcript,
    TranscriptAccessLog,
    TranscriptSegment,
)
from database.session import SessionLocal


def create_speaker(
    db: Session,
    name: str,
    phone: str | None = None
) -> Speaker:
    speaker = Speaker(
        name=name,
        phone=phone,
        kind="registered"
    )

    db.add(speaker)
    db.commit()
    db.refresh(speaker)

    return speaker


def create_anonymous_speaker(
    db: Session,
    name: str = "Unknown speaker"
) -> Speaker:
    speaker = Speaker(
        name=name,
        phone=None,
        kind="anonymous"
    )

    db.add(speaker)
    db.commit()
    db.refresh(speaker)

    return speaker


def get_speaker(
    db: Session,
    speaker_id: int
) -> Speaker | None:
    return (
        db.query(Speaker)
        .filter(Speaker.id == speaker_id)
        .first()
    )


def get_all_speakers(
    db: Session
) -> list[Speaker]:
    return (
        db.query(Speaker)
        .order_by(Speaker.id)
        .all()
    )


def get_speakers_paginated(
    db: Session,
    page: int = 1,
    page_size: int = 20
) -> dict:
    total = db.query(Speaker).count()

    offset = (page - 1) * page_size

    items = (
        db.query(Speaker)
        .order_by(Speaker.id)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    pages = ceil(total / page_size) if total else 0

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages
    }


def update_speaker(
    db: Session,
    speaker_id: int,
    name: str | None = None,
    phone: str | None = None
) -> Speaker | None:
    speaker = get_speaker(
        db=db,
        speaker_id=speaker_id
    )

    if speaker is None:
        return None

    if name is not None:
        speaker.name = name

    if phone is not None:
        speaker.phone = phone

    db.commit()
    db.refresh(speaker)

    return speaker


def delete_speaker(
    db: Session,
    speaker_id: int
) -> bool:
    speaker = get_speaker(
        db=db,
        speaker_id=speaker_id
    )

    if speaker is None:
        return False

    db.delete(speaker)
    db.commit()

    return True


def merge_speakers(
    db: Session,
    source_speaker_id: int,
    target_speaker_id: int
) -> str:
    source_speaker = get_speaker(
        db=db,
        speaker_id=source_speaker_id
    )

    if source_speaker is None:
        return "source_not_found"

    target_speaker = get_speaker(
        db=db,
        speaker_id=target_speaker_id
    )

    if target_speaker is None:
        return "target_not_found"

    (
        db.query(Recording)
        .filter(Recording.speaker_id == source_speaker_id)
        .update(
            {"speaker_id": target_speaker_id},
            synchronize_session=False
        )
    )

    (
        db.query(Occurrence)
        .filter(Occurrence.speaker_id == source_speaker_id)
        .update(
            {"speaker_id": target_speaker_id},
            synchronize_session=False
        )
    )

    (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.speaker_id == source_speaker_id)
        .update(
            {"speaker_id": target_speaker_id},
            synchronize_session=False
        )
    )

    db.delete(source_speaker)
    db.commit()

    return "merged"


def create_occurrence(
    db: Session,
    speaker_id: int,
    transcript_id: int,
    local_label: str,
    match_score: float | None = None
) -> Occurrence:
    occurrence = Occurrence(
        speaker_id=speaker_id,
        transcript_id=transcript_id,
        local_label=local_label,
        match_score=match_score
    )

    db.add(occurrence)
    db.commit()
    db.refresh(occurrence)

    return occurrence


def get_occurrences_by_speaker(
    db: Session,
    speaker_id: int
) -> list[Occurrence]:
    return (
        db.query(Occurrence)
        .filter(Occurrence.speaker_id == speaker_id)
        .order_by(Occurrence.id)
        .all()
    )


def update_segments_speaker_id(
    db: Session,
    transcript_id: int,
    local_label: str,
    speaker_id: int
) -> None:
    (
        db.query(TranscriptSegment)
        .filter(
            TranscriptSegment.transcript_id == transcript_id,
            TranscriptSegment.speaker == local_label
        )
        .update(
            {"speaker_id": speaker_id},
            synchronize_session=False
        )
    )

    db.commit()


def create_recording(
    db: Session,
    job_id: str,
    filename: str,
    speaker_id: int | None = None
) -> Recording:
    recording = Recording(
        job_id=job_id,
        filename=filename,
        speaker_id=speaker_id
    )

    db.add(recording)
    db.commit()
    db.refresh(recording)

    return recording


def get_recordings_by_speaker(
    db: Session,
    speaker_id: int
) -> list[dict]:
    rows = (
        db.query(
            Recording.job_id,
            Recording.filename,
            Recording.created_at,
            Occurrence.local_label,
            Occurrence.match_score,
        )
        .join(Transcript, Transcript.job_id == Recording.job_id)
        .join(Occurrence, Occurrence.transcript_id == Transcript.id)
        .filter(Occurrence.speaker_id == speaker_id)
        .order_by(Recording.created_at)
        .all()
    )
    return [
        {
            "job_id": r.job_id,
            "filename": r.filename,
            "created_at": r.created_at,
            "local_label": r.local_label,
            "match_score": r.match_score,
        }
        for r in rows
    ]


def get_recording_by_job_id(
    db: Session,
    job_id: str
) -> Recording | None:
    return (
        db.query(Recording)
        .filter(Recording.job_id == job_id)
        .first()
    )


def create_job(
    db: Session,
    job_id: str,
    status: str = "queued",
    audio_key: str | None = None,
    params: dict | None = None,
    idempotency_key: str | None = None
) -> Job:
    job = Job(
        id=job_id,
        status=status,
        audio_key=audio_key,
        params=params,
        idempotency_key=idempotency_key
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


def get_job_by_id(
    db: Session,
    job_id: str
) -> Job | None:
    return (
        db.query(Job)
        .filter(Job.id == job_id)
        .first()
    )


def get_job_by_idempotency_key(
    db: Session,
    idempotency_key: str
) -> Job | None:
    return (
        db.query(Job)
        .filter(Job.idempotency_key == idempotency_key)
        .first()
    )


def update_job_status(
    db: Session,
    job_id: str,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    progress: int | None = None,
) -> Job | None:
    job = get_job_by_id(db=db, job_id=job_id)

    if job is None:
        return None

    job.status = status
    job.error_code = error_code
    job.error_message = error_message

    if progress is not None:
        job.progress = progress

    if status == "processing" and job.started_at is None:
        job.started_at = datetime.utcnow()

    if status in {"done", "failed", "partial"}:
        job.finished_at = datetime.utcnow()
        if progress is None:
            job.progress = 100 if status == "done" else job.progress

    db.commit()
    db.refresh(job)

    return job


def set_job_model(db: Session, job_id: str, model_used: str) -> None:
    job = get_job_by_id(db=db, job_id=job_id)
    if job is None:
        return
    job.model_used = model_used
    db.commit()


# ---------------------------------------------------------------------------
# Transcript read/delete — session-managed (used by API routes)
# ---------------------------------------------------------------------------

def get_transcript_by_job_id(job_id: str) -> dict | None:
    db = SessionLocal()
    try:
        transcript = db.query(Transcript).filter(Transcript.job_id == job_id.strip()).first()
        if transcript is None:
            return None
        segments = (
            db.query(TranscriptSegment)
            .filter(TranscriptSegment.transcript_id == transcript.id)
            .order_by(TranscriptSegment.segment_id)
            .all()
        )
        occurrences = (
            db.query(Occurrence, Speaker)
            .join(Speaker, Occurrence.speaker_id == Speaker.id)
            .filter(Occurrence.transcript_id == transcript.id)
            .order_by(Occurrence.local_label)
            .all()
        )
        speakers = [
            {
                "local_label": occ.local_label,
                "speaker_id": spk.id,
                "display_name": spk.name if spk.kind == "registered" else None,
                "match_score": occ.match_score,
            }
            for occ, spk in occurrences
        ]
        return {
            "job_id": transcript.job_id,
            "status": transcript.status,
            "success": transcript.success,
            "language": transcript.language,
            "audio": {"duration_sec": transcript.duration_sec, "sample_rate": 16000, "channels": 1},
            "speakers": speakers,
            "transcript": {
                "full_text": transcript.full_text,
                "segments": [
                    {
                        "id": s.segment_id, "start": s.start, "end": s.end,
                        "speaker": s.speaker, "speaker_id": s.speaker_id,
                        "text": s.text, "overlap": s.overlap, "words": s.words or [],
                    }
                    for s in segments
                ],
            },
            "error": None,
        }
    finally:
        db.close()


def get_audio_key_by_job_id(job_id: str) -> str | None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id.strip()).first()
        return job.audio_key if job else None
    finally:
        db.close()


def delete_transcript_by_job_id(job_id: str) -> bool:
    db = SessionLocal()
    try:
        clean = job_id.strip()
        transcript = db.query(Transcript).filter(Transcript.job_id == clean).first()
        if transcript is None:
            return False
        recording = db.query(Recording).filter(Recording.job_id == clean).first()
        if recording is not None:
            db.delete(recording)
        db.delete(transcript)
        job = db.query(Job).filter(Job.id == clean).first()
        if job is not None:
            db.delete(job)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_transcripts(
    page: int = 1,
    page_size: int = 20,
    speaker_id: int | None = None,
    status: str | None = None,
) -> dict:
    db = SessionLocal()
    try:
        q = db.query(Transcript)
        if status is not None:
            q = q.filter(Transcript.status == status)
        if speaker_id is not None:
            sub = (
                db.query(Occurrence.transcript_id)
                .filter(Occurrence.speaker_id == speaker_id)
                .subquery()
            )
            q = q.filter(Transcript.id.in_(sub))
        total = q.count()
        items = (
            q.order_by(Transcript.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": [
                {
                    "transcript_id": t.id,
                    "job_id": t.job_id,
                    "status": t.status,
                    "language": t.language,
                    "duration_sec": t.duration_sec,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in items
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": ceil(total / page_size) if total else 0,
        }
    finally:
        db.close()


def get_segments_by_job_id(
    job_id: str,
    speaker_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict | None:
    db = SessionLocal()
    try:
        transcript = db.query(Transcript).filter(Transcript.job_id == job_id.strip()).first()
        if transcript is None:
            return None
        q = db.query(TranscriptSegment).filter(TranscriptSegment.transcript_id == transcript.id)
        if speaker_id is not None:
            q = q.filter(TranscriptSegment.speaker_id == speaker_id)
        total = q.count()
        segments = (
            q.order_by(TranscriptSegment.segment_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "job_id": transcript.job_id,
            "items": [
                {
                    "id": s.segment_id, "start": s.start, "end": s.end,
                    "speaker": s.speaker, "speaker_id": s.speaker_id,
                    "text": s.text, "overlap": s.overlap, "words": s.words or [],
                }
                for s in segments
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": ceil(total / page_size) if total else 0,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Admin user CRUD (admin_users table — new, additive)
# ---------------------------------------------------------------------------

def create_admin_user(
    db: Session,
    login: str,
    password_hash: str,
    role: str = "moderator",
) -> AdminUser:
    user = AdminUser(login=login, password_hash=password_hash, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_admin_user_by_login(db: Session, login: str) -> AdminUser | None:
    return db.query(AdminUser).filter(AdminUser.login == login).first()


def get_admin_user_by_id(db: Session, user_id: int) -> AdminUser | None:
    return db.query(AdminUser).filter(AdminUser.id == user_id).first()


def count_active_super_admins(db: Session) -> int:
    return (
        db.query(AdminUser)
        .filter(AdminUser.role == "super_admin", AdminUser.is_blocked.is_(False))
        .count()
    )


def list_admin_users(db: Session) -> list[AdminUser]:
    return db.query(AdminUser).order_by(AdminUser.created_at).all()


def update_admin_user_role(db: Session, user_id: int, new_role: str) -> AdminUser | None:
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if user is None:
        return None
    # Нельзя лишить роли последнего активного супер-админа
    if user.role == "super_admin" and new_role != "super_admin":
        if count_active_super_admins(db) <= 1:
            raise ValueError("Нельзя убрать роль у последнего активного супер-админа")
    user.role = new_role
    db.commit()
    db.refresh(user)
    return user


def set_admin_user_blocked(db: Session, user_id: int, blocked: bool) -> AdminUser | None:
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if user is None:
        return None
    # Нельзя заблокировать последнего активного супер-админа
    if user.role == "super_admin" and blocked:
        if count_active_super_admins(db) <= 1:
            raise ValueError("Нельзя заблокировать последнего активного супер-админа")
    user.is_blocked = blocked
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Audio list / detail — read-only projections (additive)
# ---------------------------------------------------------------------------

def _audio_list_filters(
    db: Session,
    query,
    date_from: datetime | None,
    date_to: datetime | None,
    status: str | None,
    speaker_id: int | None,
    q: str | None,
    job_id_q: str | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
    speaker_name: str | None = None,
    duration_min: float | None = None,
    duration_max: float | None = None,
):
    """Применяет фильтры к переданному объекту query (Transcript LEFT JOIN уже есть)."""
    if date_from:
        query = query.filter(Job.created_at >= date_from)
    if date_to:
        query = query.filter(Job.created_at <= date_to)
    if status:
        query = query.filter(Job.status == status)
    if job_id_q and job_id_q.strip():
        query = query.filter(Job.id.ilike(f"%{job_id_q.strip()}%"))
    if speaker_id is not None:
        spk_sub = (
            db.query(Transcript.job_id)
            .join(Occurrence, Occurrence.transcript_id == Transcript.id)
            .filter(Occurrence.speaker_id == speaker_id)
            .subquery()
        )
        query = query.filter(Job.id.in_(spk_sub))
    if speaker_name and speaker_name.strip():
        name_sub = (
            db.query(Transcript.job_id)
            .join(Occurrence, Occurrence.transcript_id == Transcript.id)
            .join(Speaker, Speaker.id == Occurrence.speaker_id)
            .filter(Speaker.name.ilike(f"%{speaker_name.strip()}%"))
            .subquery()
        )
        query = query.filter(Job.id.in_(name_sub))
    if min_speakers is not None or max_speakers is not None:
        spk_count_sub = (
            db.query(Job.id.label("jid"))
            .outerjoin(Transcript, Transcript.job_id == Job.id)
            .outerjoin(Occurrence, Occurrence.transcript_id == Transcript.id)
            .group_by(Job.id)
        )
        if min_speakers is not None:
            spk_count_sub = spk_count_sub.having(
                func.count(func.distinct(Occurrence.speaker_id)) >= min_speakers
            )
        if max_speakers is not None:
            spk_count_sub = spk_count_sub.having(
                func.count(func.distinct(Occurrence.speaker_id)) <= max_speakers
            )
        query = query.filter(Job.id.in_(spk_count_sub.subquery()))
    if duration_min is not None:
        query = query.filter(Transcript.duration_sec >= duration_min)
    if duration_max is not None:
        query = query.filter(Transcript.duration_sec <= duration_max)
    if q and q.strip():
        query = query.filter(Transcript.full_text.ilike(f"%{q.strip()}%"))
    return query


def list_audio(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: str | None = None,
    speaker_id: int | None = None,
    q: str | None = None,
    job_id_q: str | None = None,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
    speaker_name: str | None = None,
    duration_min: float | None = None,
    duration_max: float | None = None,
    sort_by: str = "uploaded_at",
    sort_order: str = "desc",
) -> dict:
    # Подсчёт total — без агрегата, только уникальные jobs
    count_q = (
        db.query(func.count(func.distinct(Job.id)))
        .outerjoin(Transcript, Transcript.job_id == Job.id)
        .outerjoin(Recording, Recording.job_id == Job.id)
    )
    count_q = _audio_list_filters(
        db, count_q, date_from, date_to, status, speaker_id, q,
        job_id_q, min_speakers, max_speakers, speaker_name, duration_min, duration_max,
    )
    total: int = count_q.scalar() or 0

    # Основной запрос с агрегатом speaker_count
    data_q = (
        db.query(
            Job.id.label("job_id"),
            func.coalesce(Recording.filename, Job.id).label("title"),
            Job.created_at.label("uploaded_at"),
            Transcript.duration_sec,
            Job.status,
            func.count(func.distinct(Occurrence.speaker_id)).label("speaker_count"),
        )
        .outerjoin(Transcript, Transcript.job_id == Job.id)
        .outerjoin(Recording, Recording.job_id == Job.id)
        .outerjoin(Occurrence, Occurrence.transcript_id == Transcript.id)
    )
    data_q = _audio_list_filters(
        db, data_q, date_from, date_to, status, speaker_id, q,
        job_id_q, min_speakers, max_speakers, speaker_name, duration_min, duration_max,
    )
    _sort_cols = {
        "uploaded_at": Job.created_at,
        "duration":    Transcript.duration_sec,
        "speakers":    func.count(func.distinct(Occurrence.speaker_id)),
    }
    sort_col = _sort_cols.get(sort_by, Job.created_at)
    order_expr = sort_col.asc() if sort_order == "asc" else sort_col.desc()

    rows = (
        data_q
        .group_by(
            Job.id, Job.status, Job.created_at,
            Recording.filename, Transcript.duration_sec,
        )
        .order_by(order_expr)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [
            {
                "job_id": r.job_id,
                "title": r.title,
                "uploaded_at": r.uploaded_at,
                "duration_sec": r.duration_sec,
                "status": r.status,
                "speaker_count": r.speaker_count or 0,
            }
            for r in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": ceil(total / page_size) if total else 0,
    }


def get_audio_item(db: Session, job_id: str) -> dict | None:
    row = (
        db.query(
            Job.id.label("job_id"),
            func.coalesce(Recording.filename, Job.id).label("title"),
            Job.created_at.label("uploaded_at"),
            Transcript.duration_sec,
            Job.status,
            func.count(func.distinct(Occurrence.speaker_id)).label("speaker_count"),
        )
        .outerjoin(Transcript, Transcript.job_id == Job.id)
        .outerjoin(Recording, Recording.job_id == Job.id)
        .outerjoin(Occurrence, Occurrence.transcript_id == Transcript.id)
        .filter(Job.id == job_id)
        .group_by(
            Job.id, Job.status, Job.created_at,
            Recording.filename, Transcript.duration_sec,
        )
        .first()
    )
    if row is None:
        return None
    return {
        "job_id": row.job_id,
        "title": row.title,
        "uploaded_at": row.uploaded_at,
        "duration_sec": row.duration_sec,
        "status": row.status,
        "speaker_count": row.speaker_count or 0,
    }


# ---------------------------------------------------------------------------
# Transcript reveal + audit (additive)
# ---------------------------------------------------------------------------

def create_access_log(
    db: Session,
    user_id: int,
    job_id: str,
    action: str = "reveal",
) -> TranscriptAccessLog:
    """Пишет событие раскрытия. Текст транскрипции НЕ логируется (конституция VI)."""
    log = TranscriptAccessLog(user_id=user_id, job_id=job_id, action=action)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_access_log(
    db: Session,
    page: int = 1,
    page_size: int = 50,
    user_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    q = (
        db.query(
            TranscriptAccessLog.id,
            TranscriptAccessLog.user_id,
            AdminUser.login.label("user_login"),
            TranscriptAccessLog.job_id,
            TranscriptAccessLog.action,
            TranscriptAccessLog.created_at,
        )
        .join(AdminUser, AdminUser.id == TranscriptAccessLog.user_id)
    )
    if user_id is not None:
        q = q.filter(TranscriptAccessLog.user_id == user_id)
    if date_from:
        q = q.filter(TranscriptAccessLog.created_at >= date_from)
    if date_to:
        q = q.filter(TranscriptAccessLog.created_at <= date_to)

    total: int = q.with_entities(func.count()).scalar() or 0
    rows = (
        q.order_by(TranscriptAccessLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "user_login": r.user_login,
                "job_id": r.job_id,
                "action": r.action,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": ceil(total / page_size) if total else 0,
    }


def get_transcript_reveal_data(db: Session, job_id: str) -> dict | None:
    """Возвращает сегменты + уникальные спикеры для endpoint reveal.
    None если транскрипция не существует."""
    transcript = (
        db.query(Transcript)
        .filter(Transcript.job_id == job_id)
        .first()
    )
    if transcript is None:
        return None

    segments = (
        db.query(TranscriptSegment)
        .options(joinedload(TranscriptSegment.speaker_ref))
        .filter(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.start)
        .all()
    )

    # Уникальные спикеры в порядке первого появления
    seen: dict[str, dict] = {}
    for seg in segments:
        if seg.speaker not in seen:
            display = seg.speaker_ref.name if seg.speaker_ref else None
            seen[seg.speaker] = {
                "speaker": seg.speaker,
                "speaker_id": seg.speaker_id,
                "display_name": display,
            }

    return {
        "job_id": job_id,
        "language": transcript.language,
        "speakers": list(seen.values()),
        "segments": [
            {
                "start": seg.start,
                "end": seg.end,
                "speaker": seg.speaker,
                "text": seg.text,
            }
            for seg in segments
        ],
    }


# ---------------------------------------------------------------------------
# Analytics (additive, read-only)
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset({
    # Russian
    "и", "в", "не", "на", "с", "что", "это", "по", "но", "из", "как", "а",
    "то", "все", "она", "так", "его", "да", "ты", "к", "у", "же", "ей",
    "мне", "он", "они", "бы", "за", "от", "есть", "вот", "или", "об",
    "для", "при", "ещё", "еще", "тут", "там", "её", "ее", "их", "мы",
    "вы", "нас", "вас", "им", "нет", "уже", "себя", "этот", "если",
    "чтобы", "когда", "тоже", "этого", "которые", "была", "раз", "во",
    "чем", "без", "этой", "под", "ну", "со", "до", "бы", "же", "ли",
    # English
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "it",
    "for", "not", "on", "with", "he", "as", "you", "do", "at", "this",
    "but", "his", "by", "from", "they", "we", "say", "her", "she", "or",
    "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
    "is", "was", "are", "were", "has", "had", "did", "been", "can", "its",
    "am", "into", "than", "then", "no", "our", "your", "him", "could",
})


def analytics_summary(db: Session) -> dict:
    total_audio: int = db.query(func.count(Job.id)).scalar() or 0
    total_transcribed: int = db.query(func.count(Transcript.id)).scalar() or 0
    by_status: dict[str, int] = dict(
        db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    )
    return {
        "total_audio": total_audio,
        "total_transcribed": total_transcribed,
        "by_status": by_status,
    }


def frequent_words(db: Session, limit: int = 50) -> list[dict]:
    """Топ слов через ts_stat (PostgreSQL). Фильтрует стоп-слова и токены < 3 символов."""
    sql = text("""
        SELECT word, ndoc AS count
        FROM ts_stat(
            'SELECT full_text_vector FROM transcripts WHERE full_text_vector IS NOT NULL'
        )
        WHERE char_length(word) >= 3
        ORDER BY ndoc DESC
        LIMIT :limit
    """)
    rows = db.execute(sql, {"limit": limit * 3}).fetchall()  # берём с запасом для фильтрации
    result = []
    for r in rows:
        if r.word.lower() not in _STOP_WORDS:
            result.append({"word": r.word, "count": r.count})
        if len(result) >= limit:
            break
    return result


def frequent_speakers(db: Session, limit: int = 20) -> list[dict]:
    rows = (
        db.query(
            Occurrence.speaker_id,
            Speaker.name,
            func.count(Occurrence.id).label("count"),
        )
        .join(Speaker, Speaker.id == Occurrence.speaker_id)
        .group_by(Occurrence.speaker_id, Speaker.name)
        .order_by(func.count(Occurrence.id).desc())
        .limit(limit)
        .all()
    )
    return [{"speaker_id": r.speaker_id, "name": r.name, "count": r.count} for r in rows]


def uploads_over_time(db: Session, bucket: str = "day") -> list[dict]:
    # bucket ∈ {"hour", "day"} — валидируется на уровне роутера
    trunc = func.date_trunc(bucket, Job.created_at)
    rows = (
        db.query(trunc.label("bucket"), func.count(Job.id).label("count"))
        .group_by(trunc)
        .order_by(trunc)
        .all()
    )
    return [{"bucket": r.bucket, "count": r.count} for r in rows]


# ---------------------------------------------------------------------------
# Platform settings (T040)
# ---------------------------------------------------------------------------

_DEFAULT_SETTINGS: list[dict] = [
    {"key": "default_asr_model",          "value": "",                                      "value_type": "string"},
    {"key": "default_language",           "value": "",                                      "value_type": "string"},
    {"key": "max_upload_size_mb",         "value": "2048",                                  "value_type": "int"},
    {"key": "max_speakers",               "value": "",                                      "value_type": "int"},
    {"key": "allowed_formats",            "value": "mp3,wav,ogg,flac,m4a,webm,mp4,aac,opus", "value_type": "string"},
    {"key": "audit_log_retention_days",   "value": "90",                                    "value_type": "int"},
]

_OBSOLETE_KEYS: set[str] = {"chunk_threshold_sec", "default_rate_limit"}


def _validate_setting_value(value: str, value_type: str) -> None:
    """Raises ValueError if value doesn't match value_type."""
    if value_type == "int":
        int(value)
    elif value_type == "float":
        float(value)
    elif value_type == "bool":
        if value.lower() not in ("true", "false", "1", "0"):
            raise ValueError(f"bool требует true/false/1/0, получено {value!r}")


def seed_default_settings(db: Session) -> None:
    # Удалить устаревшие ключи
    for key in _OBSOLETE_KEYS:
        row = db.query(PlatformSetting).filter_by(key=key).first()
        if row:
            db.delete(row)
    # Добавить новые если не существуют
    for s in _DEFAULT_SETTINGS:
        if not db.query(PlatformSetting).filter_by(key=s["key"]).first():
            db.add(PlatformSetting(key=s["key"], value=s["value"], value_type=s["value_type"]))
    db.commit()


def cleanup_old_audit_logs(db: Session) -> int:
    """Удаляет записи журнала старше audit_log_retention_days. Возвращает количество удалённых строк."""
    retention = get_setting_value(db, "audit_log_retention_days")
    if not retention:
        return 0
    days = int(retention)
    if days <= 0:
        return 0
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = (
        db.query(TranscriptAccessLog)
        .filter(TranscriptAccessLog.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def get_all_settings(db: Session) -> list[PlatformSetting]:
    return db.query(PlatformSetting).order_by(PlatformSetting.key).all()


def get_setting_value(db: Session, key: str) -> str | None:
    row = db.query(PlatformSetting).filter_by(key=key).first()
    return row.value if row else None


def upsert_settings(
    db: Session, updates: list[dict], updated_by: int | None = None
) -> list[PlatformSetting]:
    """Validates all updates atomically, then applies. Raises ValueError on type mismatch."""
    current = {s.key: s for s in db.query(PlatformSetting).all()}
    for u in updates:
        key, value = u["key"], u["value"]
        vtype = current[key].value_type if key in current else "string"
        _validate_setting_value(value, vtype)   # raises ValueError if bad

    now = datetime.utcnow()
    for u in updates:
        key, value = u["key"], u["value"]
        if key in current:
            current[key].value = value
            current[key].updated_at = now
            current[key].updated_by = updated_by
        else:
            db.add(PlatformSetting(key=key, value=value, value_type="string", updated_by=updated_by))
    db.commit()
    return get_all_settings(db)


# ---------------------------------------------------------------------------
# Polling notifications (T045)
# ---------------------------------------------------------------------------

def list_status_updates_since(db: Session, since: datetime) -> dict:
    rows = (
        db.query(Job.id, Job.status, Job.finished_at)
        .filter(
            Job.finished_at.isnot(None),
            Job.finished_at >= since,
            Job.status.in_(["done", "failed", "partial"]),
        )
        .order_by(Job.finished_at)
        .all()
    )
    return {
        "server_time": datetime.utcnow(),
        "items": [
            {"job_id": r.id, "status": r.status, "finished_at": r.finished_at}
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Calls (anti-scam agent)
# ---------------------------------------------------------------------------

def create_call(db: Session, call_id: str, source: str, started_at) -> Call:
    call = Call(id=call_id, source=source, started_at=started_at)
    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def add_call_event(db: Session, call_id: str, at: float, speaker: str,
                   text: str, scam_delta: int = 0) -> CallEvent:
    ev = CallEvent(call_id=call_id, at=at, speaker=speaker, text=text, scam_delta=scam_delta)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def bulk_add_call_events(
    db: Session,
    events: list[tuple[str, float, str, str, int]],
) -> None:
    """Insert multiple call events in a single transaction.

    Each element of *events* is a tuple of
    ``(call_id, at, speaker, text, scam_delta)``.
    One ``db.commit()`` is issued after all rows are added.
    """
    if not events:
        return
    db.add_all([
        CallEvent(call_id=call_id, at=at, speaker=speaker,
                  text=text, scam_delta=scam_delta)
        for call_id, at, speaker, text, scam_delta in events
    ])
    db.commit()


def finalize_call(db: Session, call_id: str, ended_at, duration_sec, verdict,
                  scenario, confidence, ended_reason, job_id, audio_key) -> Call | None:
    call = db.query(Call).filter(Call.id == call_id).first()
    if call is None:
        return None
    call.ended_at = ended_at
    call.duration_sec = duration_sec
    call.verdict = verdict
    call.scenario = scenario
    call.confidence = confidence
    call.ended_reason = ended_reason
    call.job_id = job_id
    call.audio_key = audio_key
    db.commit()
    db.refresh(call)
    return call


def set_call_summary(db: Session, call_id: str, summary: str) -> Call | None:
    call = db.query(Call).filter(Call.id == call_id).first()
    if call is None:
        return None
    call.summary = summary
    db.commit()
    db.refresh(call)
    return call


def list_calls(db: Session, page: int = 1, page_size: int = 20, verdict=None,
               scenario=None, date_from=None, date_to=None) -> dict:
    q = db.query(Call)
    if verdict:
        q = q.filter(Call.verdict == verdict)
    if scenario:
        q = q.filter(Call.scenario == scenario)
    if date_from:
        q = q.filter(Call.started_at >= date_from)
    if date_to:
        q = q.filter(Call.started_at <= date_to)
    total = q.count()
    rows = (q.order_by(Call.started_at.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    return {
        "items": [{
            "call_id": c.id, "source": c.source, "started_at": c.started_at,
            "duration_sec": c.duration_sec, "verdict": c.verdict,
            "scenario": c.scenario, "confidence": c.confidence,
        } for c in rows],
        "page": page, "page_size": page_size, "total": total,
        "pages": ceil(total / page_size) if total else 0,
    }


def get_call_detail(db: Session, call_id: str) -> dict | None:
    call = db.query(Call).filter(Call.id == call_id).first()
    if call is None:
        return None
    events = (db.query(CallEvent).filter(CallEvent.call_id == call_id)
              .order_by(CallEvent.at).all())
    return {
        "call": {
            "call_id": call.id, "source": call.source, "started_at": call.started_at,
            "ended_at": call.ended_at, "duration_sec": call.duration_sec,
            "verdict": call.verdict, "scenario": call.scenario,
            "confidence": call.confidence, "ended_reason": call.ended_reason,
            "job_id": call.job_id, "summary": call.summary, "audio_key": call.audio_key,
        },
        "events": [{"at": e.at, "speaker": e.speaker, "text": e.text,
                    "scam_delta": e.scam_delta} for e in events],
    }
