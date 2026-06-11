from fastapi import FastAPI

from api.routes import api_router


app = FastAPI(
    title="Audio Intelligence API",
    description=(
        "API for asynchronous audio transcription, "
        "speaker diarization and transcript search."
    ),
    version="1.0.0"
)

app.include_router(api_router)