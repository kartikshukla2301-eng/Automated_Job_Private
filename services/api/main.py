"""FastAPI application entrypoint and route declarations."""

from fastapi import FastAPI

from services.api.config import Settings, settings
from services.api.logging_config import RequestCorrelationMiddleware, setup_logging
from services.api.schemas import HealthResponse


def create_app(app_settings: Settings = settings) -> FastAPI:
    """Factory creating and configuring the FastAPI application."""
    # Initialize structured JSON logging
    setup_logging(service_name="job-agent-api", log_level=app_settings.log_level)

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
    )

    # Attach request correlation and structured HTTP access logging
    app.add_middleware(RequestCorrelationMiddleware)

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
