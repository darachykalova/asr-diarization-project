import logging

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from api.routes import api_router


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
async def warmup_models():
    from services.text_embedding_service import TextEmbeddingService

    logger = logging.getLogger(__name__)

    logger.info("Preloading SentenceTransformer model...")

    await run_in_threadpool(TextEmbeddingService)

    logger.info("SentenceTransformer model loaded.")


app.include_router(api_router)