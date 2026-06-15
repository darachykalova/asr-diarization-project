from fastapi import APIRouter

from api.routes.calls import router as calls_router
from api.routes.health import router as health_router
from api.routes.jobs import router as jobs_router
from api.routes.speakers import router as speakers_router
from api.routes.transcriptions import router as transcriptions_router
from api.routes.transcripts import router as transcripts_router


api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(transcriptions_router)
api_router.include_router(jobs_router)
api_router.include_router(transcripts_router)
api_router.include_router(calls_router)
api_router.include_router(speakers_router)