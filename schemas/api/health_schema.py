from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(
        ...,
        description="API health status."
    )
    service: str = Field(
        ...,
        description="Service name."
    )