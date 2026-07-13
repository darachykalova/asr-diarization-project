"""FastAPI service: one WebSocket endpoint drives a live call."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from call_agent.config import get_settings
from call_agent.scam_detector import load_scenarios, ScamDetector
from call_agent.dialog_engine import load_replies, DialogEngine
from call_agent.semantic_check import check_scam_semantically
from call_agent.streaming_asr import StreamingASR
from call_agent.tts_service import TTSService
from call_agent.recorder import CallRecorder
from call_agent.session import CallSession
from clients.minio_client import MinioStorageClient
from database.session import SessionLocal
from database import crud
from tasks.audio_tasks import build_pipeline_chain

settings = get_settings()
app = FastAPI(title="Call Agent")
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    _check_call_agent_models()
    app.state.replies = load_replies(settings.replies_path)
    app.state.scenarios = load_scenarios(settings.scenarios_dir)
    app.state.tts = TTSService(settings)
    app.state.semantic_executor = ThreadPoolExecutor(max_workers=2)
    # Pre-synthesize every canned phrase so calls have zero TTS latency.
    canned = (app.state.replies["greeting"] + app.state.replies["fillers"]
              + app.state.replies["keep_talking"] + app.state.replies["take_message"]
              + app.state.replies["before_hangup"])
    app.state.tts.warm_cache(canned)
    from vosk import Model
    app.state.vosk_model = Model(settings.vosk_model_path)


def _new_recognizer():
    from vosk import KaldiRecognizer
    rec = KaldiRecognizer(app.state.vosk_model, 16000)
    rec.SetWords(True)
    return rec


def _submit_semantic_check(transcript: str):
    return app.state.semantic_executor.submit(check_scam_semantically, transcript, settings)


@app.get("/health")
def health():
    return {"status": "ok"}


def _read_wav_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Model readiness check — called at startup so the container fails fast.
# ---------------------------------------------------------------------------

def _check_call_agent_models() -> None:
    """Fail fast if Vosk or Silero models are missing."""
    import sys
    from pathlib import Path

    errors: list[str] = []

    vosk_path = Path(settings.vosk_model_path)
    if not vosk_path.is_dir() or not any(vosk_path.rglob("final.mdl")):
        errors.append(
            f"Vosk model not found or incomplete at: {vosk_path}\n"
            "  Download: https://alphacephei.com/vosk/models\n"
            "  Example:  wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip\n"
            "            unzip vosk-model-small-ru-0.22.zip -d <models_cache>/vosk/\n"
            f"  Expected: {vosk_path}/am/final.mdl"
        )

    silero_path = Path(settings.silero_model_path)
    if not silero_path.exists():
        errors.append(
            f"Silero TTS model not found at: {silero_path}\n"
            "  Download: python -c \"import torch; torch.hub.download_url_to_file("
            "'https://models.silero.ai/models/tts/ru/v4_ru.pt', '<path>')\"\n"
            f"  Expected: {silero_path}"
        )

    if errors:
        print("=" * 70)
        print("CALL-AGENT MODEL VERIFICATION FAILED")
        print("=" * 70)
        for err in errors:
            print(f"[MISSING] {err}")
        print("=" * 70)
        print("Run: docker compose exec call-agent python scripts/verify_call_agent_models.py")
        print("=" * 70)
        sys.exit(1)


@app.websocket("/ws/call")
async def ws_call(ws: WebSocket):
    await ws.accept()
    call_id = str(uuid.uuid4())
    db = SessionLocal()
    recorder = CallRecorder(call_id)
    events: list[tuple] = []

    def on_event(at, speaker, text, delta):
        events.append((at, speaker, text, delta))

    crud.create_call(db, call_id, source="browser", started_at=datetime.utcnow())
    asr = StreamingASR(settings, recognizer=_new_recognizer())
    detector = ScamDetector(app.state.scenarios)
    dialog = DialogEngine(app.state.replies)
    session = CallSession(call_id, asr, detector, dialog, app.state.tts, recorder,
                          on_event=on_event, check_submitter=_submit_semantic_check)

    async def send_action(action):
        if action.type == "speak":
            await ws.send_json({"type": "agent_text", "text": action.text})
            # Fix 1: _read_wav_bytes is blocking I/O — run in thread pool
            wav = await asyncio.to_thread(_read_wav_bytes, action.wav_path)
            recorder.write_agent(_pcm_from_wav(wav))
            await ws.send_bytes(wav)
        elif action.type == "hangup":
            await ws.send_json({"type": "hangup"})

    ended_reason = "caller_hung_up"
    try:
        # Fix 1: session.start() calls TTS synthesis — run in thread pool
        greeting = await asyncio.to_thread(session.start)
        await send_action(greeting)

        while True:
            chunk = await ws.receive_bytes()
            # Fix 1: on_pcm runs Vosk AcceptWaveform (CPU-bound) — run in thread pool
            actions = await asyncio.to_thread(session.on_pcm, chunk)
            for a in actions:
                await send_action(a)
                if a.type == "hangup":
                    ended_reason = "detected_scam"
                    raise WebSocketDisconnect()
            # Fix 1: tick may run TTS synthesis — run in thread pool
            tick_actions = await asyncio.to_thread(session.tick, settings.not_scam_timeout_sec)
            for a in tick_actions:
                await send_action(a)
                if a.type == "hangup":
                    ended_reason = "detected_scam"
                    raise WebSocketDisconnect()
    except WebSocketDisconnect:
        pass
    except Exception:
        # Abrupt client disconnects surface as ConnectionClosedError/RuntimeError
        # from send calls, not WebSocketDisconnect — log and finalize normally.
        logger.exception("ws_call: connection error for call %s", call_id)
    finally:
        # Fix 3: exception isolation — best-effort finalize even if _finalize raises
        await _safe_finalize(session, db, recorder, call_id, events, ended_reason)
        db.close()


def _pcm_from_wav(wav_bytes: bytes) -> bytes:
    # Strip 44-byte WAV header to get raw PCM for the mixed recording track.
    return wav_bytes[44:]


def _send_call_alert(webhook_url: str | None, call_id: str, verdict: str) -> None:
    if not webhook_url:
        return
    try:
        from services.webhook_service import send_webhook
        send_webhook(url=webhook_url, payload={"call_id": call_id, "verdict": verdict})
    except Exception as exc:
        logger.warning("Call %s: n8n alert webhook failed: %s", call_id, exc)


def _finalize(session, db, recorder, call_id, events, ended_reason):
    """Synchronous finalize — called via asyncio.to_thread from _safe_finalize."""
    result = session.result()
    if result.verdict == "scam":
        ended_reason = "detected_scam"
    local = recorder.close()
    duration_sec = _wav_duration(local)
    minio = MinioStorageClient()
    object_key, job_id = recorder.publish(minio, db)

    # Fix 2: batch all call events in a single transaction instead of one commit per event
    event_objs = []
    from database.models import CallEvent
    for at, speaker, text, delta in events:
        event_objs.append(CallEvent(call_id=call_id, at=at, speaker=speaker,
                                    text=text, scam_delta=delta))
    if event_objs:
        db.add_all(event_objs)
        db.flush()  # write to DB but let finalize_call do the single commit below

    crud.finalize_call(db, call_id, ended_at=datetime.utcnow(), duration_sec=duration_sec,
                       verdict=result.verdict, scenario=result.scenario,
                       confidence=result.confidence, ended_reason=result.ended_reason or ended_reason,
                       job_id=job_id, audio_key=object_key)
    # finalize_call already calls db.commit(), which commits events + call row together
    build_pipeline_chain(job_id=job_id, input_key=object_key).apply_async(task_id=job_id)
    _send_call_alert(settings.n8n_call_alert_webhook_url, call_id, result.verdict)


async def _safe_finalize(session, db, recorder, call_id, events, ended_reason):
    """Fix 3: Wrap _finalize so that even on failure the DB row is updated with what we know."""
    try:
        # Fix 1: _finalize is blocking (MinIO upload, DB commits, Celery dispatch) — run in thread
        await asyncio.to_thread(_finalize, session, db, recorder, call_id, events, ended_reason)
    except Exception as exc:
        logger.exception("_finalize failed for call %s: %s", call_id, exc)
        # Best-effort: at least mark the call as ended in the DB
        try:
            result = session.result()
            await asyncio.to_thread(
                crud.finalize_call,
                db,
                call_id=call_id,
                ended_at=datetime.utcnow(),
                duration_sec=None,
                verdict=result.verdict or "undetermined",
                scenario=result.scenario,
                confidence=result.confidence,
                ended_reason=ended_reason,
                job_id=None,
                audio_key=None,  # upload failed
            )
        except Exception:
            pass
        raise  # re-raise so the error is still logged by FastAPI


def _wav_duration(path: str) -> float:
    import wave
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())
