"""FastAPI service: one WebSocket endpoint drives a live call."""
from __future__ import annotations

import os
import uuid
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from call_agent.config import get_settings
from call_agent.scam_detector import load_scenarios, ScamDetector
from call_agent.dialog_engine import load_replies, DialogEngine
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    app.state.replies = load_replies(settings.replies_path)
    app.state.scenarios = load_scenarios(settings.scenarios_dir)
    app.state.tts = TTSService(settings)
    # Pre-synthesize every canned phrase so calls have zero TTS latency.
    canned = (app.state.replies["greeting"] + app.state.replies["fillers"]
              + app.state.replies["keep_talking"] + app.state.replies["take_message"])
    app.state.tts.warm_cache(canned)
    from vosk import Model
    app.state.vosk_model = Model(settings.vosk_model_path)


def _new_recognizer():
    from vosk import KaldiRecognizer
    rec = KaldiRecognizer(app.state.vosk_model, 16000)
    rec.SetWords(True)
    return rec


@app.get("/health")
def health():
    return {"status": "ok"}


def _read_wav_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


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
                          on_event=on_event)

    async def send_action(action):
        if action.type == "speak":
            await ws.send_json({"type": "agent_text", "text": action.text})
            wav = _read_wav_bytes(action.wav_path)
            recorder.write_agent(_pcm_from_wav(wav))
            await ws.send_bytes(wav)
        elif action.type == "hangup":
            await ws.send_json({"type": "hangup"})

    await send_action(session.start())

    ended_reason = "caller_hung_up"
    try:
        while True:
            chunk = await ws.receive_bytes()
            actions = session.on_pcm(chunk)
            for a in actions:
                await send_action(a)
                if a.type == "hangup":
                    ended_reason = "detected_scam"
                    raise WebSocketDisconnect()
            tick = session.tick(settings.not_scam_timeout_sec)
            if tick is not None:
                await send_action(tick)
    except WebSocketDisconnect:
        pass
    finally:
        _finalize(db, recorder, session, call_id, events, ended_reason)
        db.close()


def _pcm_from_wav(wav_bytes: bytes) -> bytes:
    # Strip 44-byte WAV header to get raw PCM for the mixed recording track.
    return wav_bytes[44:]


def _finalize(db, recorder, session, call_id, events, ended_reason):
    result = session.result()
    if result.verdict == "scam":
        ended_reason = "detected_scam"
    local = recorder.close()
    duration_sec = _wav_duration(local)
    minio = MinioStorageClient()
    object_key, job_id = recorder.publish(minio, db)
    for at, speaker, text, delta in events:
        crud.add_call_event(db, call_id, at, speaker, text, delta)
    crud.finalize_call(db, call_id, ended_at=datetime.utcnow(), duration_sec=duration_sec,
                       verdict=result.verdict, scenario=result.scenario,
                       confidence=result.confidence, ended_reason=result.ended_reason or ended_reason,
                       job_id=job_id, audio_key=object_key)
    build_pipeline_chain(job_id=job_id, input_key=object_key).apply_async(task_id=job_id)


def _wav_duration(path: str) -> float:
    import wave
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())
