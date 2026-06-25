from fastapi import APIRouter

from api.routes.api_keys import router as api_keys_router
from api.routes.health import router as health_router
from api.routes.jobs import router as jobs_router
from api.routes.search import router as search_router
from api.routes.speakers import router as speakers_router
from api.routes.transcriptions import router as transcriptions_router
from api.routes.transcripts import router as transcripts_router


api_router = APIRouter(prefix="/v1")

api_router.include_router(transcriptions_router)
api_router.include_router(jobs_router)
api_router.include_router(transcripts_router)
api_router.include_router(speakers_router)
api_router.include_router(api_keys_router)
api_router.include_router(search_router)
