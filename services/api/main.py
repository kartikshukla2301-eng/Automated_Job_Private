"""FastAPI application entrypoint and route declarations."""

from fastapi import FastAPI

from services.api.config import Settings, settings
from services.api.schemas import HealthResponse


def create_app(app_settings: Settings = settings) -> FastAPI:
    """Factory creating and configuring the FastAPI application."""
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
    )

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Service Health Check",
        description="Returns service health status without disclosing internal paths, keys, or credentials.",
    )
    async def get_health() -> HealthResponse:
        return HealthResponse(
            status="healthy",
            service="job-agent-api",
            version=app_settings.app_version,
            environment=app_settings.app_env,
        )

    return app


app = create_app()
