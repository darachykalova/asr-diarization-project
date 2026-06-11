from fastapi import APIRouter

from schemas.api.health_schema import HealthResponse


router = APIRouter(
    tags=["Health"]
)


@router.get(
    "/",
    response_model=HealthResponse,
    summary="Health check",
    description="Checks whether the API service is running."
)
def health_check():
    return {
        "status": "ok",
        "service": "Audio Intelligence API"
    }