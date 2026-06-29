"""
Celery pipeline tasks — split pipeline for chain execution.

Each task receives a context dict from the previous task and returns an enriched
context dict. The chain is assembled in build_pipeline_chain() in audio_tasks.py.

Context keys added by each task:
  normalize_task       → normalized_path
  asr_task             → asr_segments, detected_language, duration_sec
  diarize_task         → speaker_segments, diarization_error
  merge_align_task     → aligned_segments, full_text
  persist_task         → transcript_id, final_status
  identify_speakers_task → (creates DB occurrences + Qdrant vectors, no new keys)
  finalize_task        → (updates job status, fires webhook)
"""

import logging
import shutil
import tempfile
from pathlib import Path

from celery_app.app import celery_app
from database.session import SessionLocal
from database import crud

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_progress(job_id: str, progress: int) -> None:
    db = SessionLocal()
    try:
        crud.update_job_status(db=db, job_id=job_id, status="processing", progress=progress)
    except Exception:
        pass
    finally:
        db.close()


def _set_status(job_id: str, status: str, error_code: str | None = None,
                error_message: str | None = None, progress: int | None = None) -> None:
    db = SessionLocal()
    try:
        crud.update_job_status(db=db, job_id=job_id, status=status,
                               error_code=error_code, error_message=error_message,
                               progress=progress)
    except Exception:
        pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task 1 — normalize
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="pipeline.normalize",
    autoretry_for=(OSError, IOError),
    max_retries=2,
    retry_backoff=True,
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def normalize_task(self, ctx: dict) -> dict:
    job_id = ctx["job_id"]
    input_key = ctx["input_key"]
    _set_progress(job_id, 5)

    from clients.minio_client import MinioStorageClient
    from services.audio_service import normalize_audio

    suffix = Path(input_key).suffix or ".bin"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    try:
        MinioStorageClient().download_file(object_key=input_key, local_path=tmp.name)

        normalized_path = str(Path("data/normalized/jobs") / job_id / "audio_16k_mono.wav")
        Path(normalized_path).parent.mkdir(parents=True, exist_ok=True)
        normalize_audio(input_path=tmp.name, output_path=normalized_path)
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    _set_progress(job_id, 15)
    ctx["normalized_path"] = normalized_path
    return ctx


# ---------------------------------------------------------------------------
# Task 2 — ASR (Whisper)
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="pipeline.asr",
    autoretry_for=(RuntimeError,),
    max_retries=2,
    retry_backoff=True,
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def asr_task(self, ctx: dict) -> dict:
    job_id = ctx["job_id"]
    params = ctx["params"]
    _set_progress(job_id, 20)

    from services.asr_service import ASRService
    from services.audio_quality_service import compute_snr_db, select_model_by_snr
    from services.chunking_service import delete_chunk_files, split_audio
    from services.model_cache import is_whisper_available

    normalized_path = ctx["normalized_path"]
    override = params.get("whisper_model")

    def _resolve_model(path: str) -> str:
        if override:
            m = override
            logger.info("Job %s: user-selected model '%s'", job_id, m)
        else:
            snr_db = compute_snr_db(path)
            m = select_model_by_snr(snr_db)
            logger.info("Job %s: SNR=%.1f dB -> auto model '%s'", job_id, snr_db, m)
        if not is_whisper_available(m):
            logger.warning("Job %s: model '%s' unavailable, falling back to 'base'", job_id, m)
            m = "base"
        return m

    _MODEL_TIER = {"tiny": 0, "base": 1, "large-v2": 2}

    chunks = split_audio(normalized_path)
    try:
        if len(chunks) == 1:
            model_size = _resolve_model(normalized_path)
            segments, language, duration = ASRService(model_size).transcribe(
                audio_path=normalized_path,
                language=params.get("language"),
                initial_prompt=params.get("initial_prompt"),
            )
            models_used = [model_size]
        else:
            all_segments: list[dict] = []
            languages: list[str] = []
            total_duration = 0.0
            models_used = []

            for idx, (chunk_path, offset_sec) in enumerate(chunks):
                model_size = _resolve_model(chunk_path)
                chunk_segs, chunk_lang, chunk_dur = ASRService(model_size).transcribe(
                    audio_path=chunk_path,
                    language=params.get("language"),
                    initial_prompt=params.get("initial_prompt"),
                )
                for seg in chunk_segs:
                    seg["start"] = round(seg["start"] + offset_sec, 2)
                    seg["end"] = round(seg["end"] + offset_sec, 2)
                    for w in seg.get("words", []):
                        w["start"] = round(w["start"] + offset_sec, 2)
                        w["end"] = round(w["end"] + offset_sec, 2)
                all_segments.extend(chunk_segs)
                if chunk_lang:
                    languages.append(chunk_lang)
                if chunk_dur:
                    total_duration += chunk_dur
                models_used.append(model_size)
                logger.info("Job %s: chunk %d/%d done (model=%s)", job_id, idx + 1, len(chunks), model_size)

            segments = all_segments
            language = max(set(languages), key=languages.count) if languages else None
            duration = total_duration
    finally:
        delete_chunk_files(chunks, normalized_path)

    model_used = max(models_used, key=lambda m: _MODEL_TIER.get(m, 0))

    db = SessionLocal()
    try:
        crud.set_job_model(db=db, job_id=job_id, model_used=model_used)
    except Exception:
        pass
    finally:
        db.close()

    _set_progress(job_id, 45)
    ctx["model_used"] = model_used
    ctx["asr_segments"] = segments
    ctx["detected_language"] = language
    ctx["duration_sec"] = duration
    return ctx


# ---------------------------------------------------------------------------
# Task 3 — diarize (pyannote or single-speaker shortcut)
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="pipeline.diarize",
    max_retries=1,
    retry_backoff=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def diarize_task(self, ctx: dict) -> dict:
    job_id = ctx["job_id"]
    params = ctx["params"]
    asr_segments = ctx["asr_segments"]
    duration_sec = ctx.get("duration_sec") or 0.0
    max_speakers = params.get("max_speakers")
    _set_progress(job_id, 50)

    if max_speakers == 1:
        start = float(asr_segments[0]["start"]) if asr_segments else 0.0
        end = float(asr_segments[-1]["end"]) if asr_segments else duration_sec
        ctx["speaker_segments"] = [{
            "start": start, "end": end,
            "speaker": "SPEAKER_00", "diarization_source": "single_speaker",
        }]
        ctx["diarization_error"] = None
        logger.info("Job %s: single-speaker mode, skipped pyannote", job_id)
    else:
        try:
            from services.vad_service import VADService
            from services.diarization_service import DiarizationService
            speech_segs = VADService().detect_speech(ctx["normalized_path"])
            ctx["speaker_segments"] = DiarizationService().diarize(
                audio_path=ctx["normalized_path"],
                speech_segments=speech_segs,
                min_speakers=params.get("min_speakers"),
                max_speakers=max_speakers,
            )
            ctx["diarization_error"] = None
        except Exception as exc:
            logger.warning("Job %s: diarization failed, continuing without speakers: %s", job_id, exc)
            ctx["speaker_segments"] = []
            ctx["diarization_error"] = str(exc)

    _set_progress(job_id, 65)
    return ctx


# ---------------------------------------------------------------------------
# Task 4 — merge + align
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="pipeline.merge_align",
    max_retries=1,
    acks_late=True,
    reject_on_worker_lost=True,
)
def merge_align_task(self, ctx: dict) -> dict:
    job_id = ctx["job_id"]
    _set_progress(job_id, 70)

    from services.diarization_service import DiarizationService
    from services.alignment_service import AlignmentService

    diarized = DiarizationService().assign_speakers_to_asr_segments(
        asr_segments=ctx["asr_segments"],
        speaker_segments=ctx["speaker_segments"],
    )
    aligned = AlignmentService().align(segments=diarized)

    ctx["aligned_segments"] = aligned
    ctx["full_text"] = " ".join(s["text"] for s in aligned)
    _set_progress(job_id, 75)
    return ctx


# ---------------------------------------------------------------------------
# Task 5 — persist to Postgres
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="pipeline.persist",
    autoretry_for=(Exception,),
    max_retries=2,
    retry_backoff=True,
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def persist_task(self, ctx: dict) -> dict:
    job_id = ctx["job_id"]
    aligned_segments = ctx["aligned_segments"]
    full_text = ctx.get("full_text", "")
    diarization_error = ctx.get("diarization_error")
    _set_progress(job_id, 80)

    from sqlalchemy import func
    from database.models import Transcript, TranscriptSegment

    final_status = "partial" if diarization_error else "done"

    db = SessionLocal()
    try:
        existing = db.query(Transcript).filter(Transcript.job_id == job_id).first()
        if existing:
            db.delete(existing)
            db.commit()

        transcript = Transcript(
            job_id=job_id,
            status=final_status,
            success=True,
            full_text=full_text,
            full_text_vector=func.to_tsvector("simple", full_text),
            language=ctx.get("detected_language"),
            duration_sec=ctx.get("duration_sec"),
        )
        db.add(transcript)
        db.flush()

        for seg in aligned_segments:
            words_json = [
                {
                    "w": w.get("word", w.get("w", "")),
                    "start": w.get("start", 0),
                    "end": w.get("end", 0),
                    "conf": w.get("confidence", w.get("conf", 0)),
                }
                for w in seg.get("words", [])
            ]
            db.add(TranscriptSegment(
                transcript_id=transcript.id,
                segment_id=seg["id"],
                speaker=seg["speaker"],
                speaker_id=None,
                start=seg["start"],
                end=seg["end"],
                text=seg["text"],
                overlap=seg.get("overlap", False),
                words=words_json,
            ))

        db.commit()
        ctx["transcript_id"] = transcript.id
        ctx["final_status"] = final_status
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    _set_progress(job_id, 88)
    return ctx


# ---------------------------------------------------------------------------
# Task 6 — identify speakers + save Qdrant text vectors
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="pipeline.identify_speakers",
    max_retries=1,
    acks_late=True,
    reject_on_worker_lost=True,
)
def identify_speakers_task(self, ctx: dict) -> dict:
    job_id = ctx["job_id"]
    transcript_id = ctx.get("transcript_id")
    normalized_path = ctx.get("normalized_path", "")
    speaker_segments = ctx.get("speaker_segments", [])
    aligned_segments = ctx.get("aligned_segments", [])
    _set_progress(job_id, 90)

    if transcript_id is None:
        logger.warning("Job %s: no transcript_id, skipping speaker identification", job_id)
        return ctx

    # --- voice embedding + speaker matching ---
    _identify_speakers(job_id, transcript_id, normalized_path, speaker_segments)

    # --- save text vectors to Qdrant ---
    _save_text_vectors(job_id, aligned_segments)

    _set_progress(job_id, 97)
    return ctx


def _identify_speakers(job_id: str, transcript_id: int,
                        normalized_audio: str, speaker_segments: list[dict]) -> None:
    labels = sorted({s["speaker"] for s in speaker_segments if s.get("speaker")})
    if not labels:
        return

    try:
        from services.voice_embedding_service import VoiceEmbeddingService
        from services.speaker_identification_service import SpeakerIdentificationService
        from services.audio_segment_extractor import extract_longest_segment

        voice_svc = VoiceEmbeddingService()
        if not voice_svc.is_available():
            _assign_anonymous(job_id, transcript_id, labels)
            return

        ident_svc = SpeakerIdentificationService()
        db = SessionLocal()
        seen_speaker_ids: set[int] = set()

        try:
            for label in labels:
                clip_path = str(Path("data/temp_voice") / job_id / f"{label}.wav")
                extracted = extract_longest_segment(
                    audio_path=normalized_audio,
                    segments=speaker_segments,
                    speaker_label=label,
                    output_path=clip_path,
                    min_duration=3.0,
                )

                if extracted is None:
                    speaker = crud.create_anonymous_speaker(db=db, name=f"Unknown speaker {label}")
                    match_score = None
                else:
                    embedding = voice_svc.extract_embedding(extracted)
                    if embedding is None:
                        speaker = crud.create_anonymous_speaker(db=db, name=f"Unknown speaker {label}")
                        match_score = None
                    else:
                        speaker_id, match_score = ident_svc.find_speaker(
                            embedding=embedding, excluded_speaker_ids=seen_speaker_ids
                        )
                        if speaker_id is None:
                            speaker = crud.create_anonymous_speaker(db=db, name=f"Unknown speaker {label}")
                            ident_svc.save_embedding(speaker_id=speaker.id, embedding=embedding)
                        else:
                            speaker = crud.get_speaker(db=db, speaker_id=speaker_id)
                            if speaker is None:
                                speaker = crud.create_anonymous_speaker(db=db, name=f"Unknown speaker {label}")
                                ident_svc.save_embedding(speaker_id=speaker.id, embedding=embedding)
                                match_score = None

                seen_speaker_ids.add(speaker.id)
                crud.create_occurrence(db=db, speaker_id=speaker.id, transcript_id=transcript_id,
                                       local_label=label, match_score=match_score)
                crud.update_segments_speaker_id(db=db, transcript_id=transcript_id,
                                                local_label=label, speaker_id=speaker.id)
                logger.info("Job %s: %s → speaker_id=%s score=%s", job_id, label, speaker.id, match_score)
        finally:
            db.close()
            shutil.rmtree(Path("data/temp_voice") / job_id, ignore_errors=True)

    except Exception as exc:
        logger.warning("Job %s: speaker identification failed: %s", job_id, exc)


def _assign_anonymous(job_id: str, transcript_id: int, labels: list[str]) -> None:
    db = SessionLocal()
    try:
        for label in labels:
            speaker = crud.create_anonymous_speaker(db=db, name=f"Unknown speaker {label}")
            crud.create_occurrence(db=db, speaker_id=speaker.id, transcript_id=transcript_id,
                                   local_label=label, match_score=None)
            crud.update_segments_speaker_id(db=db, transcript_id=transcript_id,
                                            local_label=label, speaker_id=speaker.id)
    finally:
        db.close()


def _save_text_vectors(job_id: str, aligned_segments: list[dict]) -> None:
    try:
        from services.qdrant_service import QdrantService
        from types import SimpleNamespace

        seg_objects = [
            SimpleNamespace(
                id=s["id"], text=s["text"], speaker=s["speaker"],
                start=s["start"], end=s["end"],
            )
            for s in aligned_segments
        ]
        QdrantService().save_segments(job_id=job_id, segments=seg_objects)
        logger.info("Job %s: text vectors saved to Qdrant", job_id)
    except Exception as exc:
        logger.warning("Job %s: Qdrant text save failed (non-fatal): %s", job_id, exc)


# ---------------------------------------------------------------------------
# Task 7 — finalize: update job status + webhook
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name="pipeline.finalize",
    max_retries=2,
    retry_backoff=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def finalize_task(self, ctx: dict) -> dict:
    job_id = ctx["job_id"]
    final_status = ctx.get("final_status", "done")
    diarization_error = ctx.get("diarization_error")
    webhook_url = ctx.get("params", {}).get("webhook_url")

    _set_status(
        job_id=job_id,
        status=final_status,
        error_code="PARTIAL_RESULT" if final_status == "partial" else None,
        error_message=diarization_error,
        progress=100,
    )

    if webhook_url:
        try:
            from services.webhook_service import send_webhook
            send_webhook(url=webhook_url, payload={"job_id": job_id, "status": final_status})
        except Exception as exc:
            logger.warning("Job %s: webhook failed: %s", job_id, exc)

    logger.info("Job %s: pipeline chain finished with status=%s", job_id, final_status)
    return ctx


# ---------------------------------------------------------------------------
# Chain error handler — marks job failed if any task in the chain crashes
# ---------------------------------------------------------------------------

@celery_app.task(name="pipeline.chain_error_handler")
def chain_error_handler(request, exc, traceback, job_id: str) -> None:
    logger.error("Job %s: pipeline chain failed: %s", job_id, exc)
    _set_status(
        job_id=job_id,
        status="failed",
        error_code="PIPELINE_CHAIN_FAILED",
        error_message=str(exc),
    )
