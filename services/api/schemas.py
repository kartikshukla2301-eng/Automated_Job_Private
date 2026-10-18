"""Pydantic schemas for FastAPI endpoints."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for GET /health response."""

    status: str = Field(..., description="Service health status", examples=["healthy"])
    service: str = Field(..., description="Service identifier", examples=["job-agent-api"])
    version: str = Field(..., description="Service semantic version", examples=["0.1.0"])
    environment: str = Field(..., description="Operating environment", examples=["development"])
