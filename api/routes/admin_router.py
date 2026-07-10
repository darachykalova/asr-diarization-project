from fastapi import APIRouter

from api.routes.admin_analytics import router as admin_analytics_router
from api.routes.admin_audio import router as admin_audio_router
from api.routes.admin_audit import router as admin_audit_router
from api.routes.admin_auth import router as admin_auth_router
from api.routes.admin_calls import router as admin_calls_router
from api.routes.admin_settings import router as admin_settings_router
from api.routes.admin_transcript import router as admin_transcript_router
from api.routes.admin_users import router as admin_users_router

admin_router = APIRouter(prefix="/admin")

admin_router.include_router(admin_auth_router)
admin_router.include_router(admin_audio_router)
admin_router.include_router(admin_transcript_router)
admin_router.include_router(admin_users_router)
admin_router.include_router(admin_audit_router)
admin_router.include_router(admin_analytics_router)
admin_router.include_router(admin_settings_router)
admin_router.include_router(admin_calls_router)
