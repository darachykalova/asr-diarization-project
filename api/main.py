import logging

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from api.routes import api_router
from database.init_db import init_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


app = FastAPI(
    title="Audio Intelligence API",
    description=(
        "API for asynchronous audio transcription, "
        "speaker diarization and transcript search."
    ),
    version="1.0.0"
)


@app.on_event("startup")
async def startup():
    logger = logging.getLogger(__name__)

    logger.info("Initializing database tables...")
    await run_in_threadpool(init_db)
    logger.info("Database tables initialized.")

    from services.text_embedding_service import TextEmbeddingService

    logger.info("Preloading SentenceTransformer model...")
    await run_in_threadpool(TextEmbeddingService)
    logger.info("SentenceTransformer model loaded.")


app.include_router(api_router)