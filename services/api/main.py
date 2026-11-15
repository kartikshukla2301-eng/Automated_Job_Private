"""FastAPI application entrypoint and route declarations."""

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse

from services.api.config import Settings, get_settings, settings
from services.api.logging_config import RequestCorrelationMiddleware, setup_logging
from services.api.routes.applications import router as applications_router
from services.api.routes.dry_run import router as dry_run_router
from services.api.routes.ops import router as ops_router
from services.api.routes.pilot import router as pilot_router
from services.api.routes.dashboard import router as dashboard_router
from services.api.schemas import HealthResponse
from worker.application.exceptions import (
    ApprovalRequiredError,
    InvalidStateTransitionError,
    TerminalStateError,
)
from worker.core.exceptions import (
    CapExceededError,
    InvalidSafetyStateError,
    KillSwitchActiveError,
    RealSubmitGateBlockedError,
    SafetyBlockedError,
)


def create_app(app_settings: Settings = settings) -> FastAPI:
    """Factory creating and configuring the FastAPI application."""
    # Initialize structured JSON logging
    setup_logging(service_name="job-agent-api", log_level=app_settings.log_level)

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
    )

    # Bind settings cleanly to application state rather than mutating dependency_overrides
    app.state.settings = app_settings

    # Attach request correlation and structured HTTP access logging
    app.add_middleware(RequestCorrelationMiddleware)

    # Register safety exception handlers
    @app.exception_handler(KillSwitchActiveError)
    async def kill_switch_exception_handler(_: Request, exc: KillSwitchActiveError):
        return JSONResponse(
            status_code=status.HTTP_423_LOCKED,
            content={"error": "kill_switch_active", "detail": str(exc), "blocked_by": "kill_switch"},
        )

    @app.exception_handler(CapExceededError)
    async def cap_exceeded_exception_handler(_: Request, exc: CapExceededError):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "cap_exceeded", "detail": str(exc), "blocked_by": "application_caps"},
        )

    @app.exception_handler(InvalidSafetyStateError)
    async def invalid_safety_state_exception_handler(_: Request, exc: InvalidSafetyStateError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "invalid_safety_state", "detail": str(exc), "blocked_by": "invalid_safety_state"},
        )

    @app.exception_handler(RealSubmitGateBlockedError)
    async def real_submit_gate_exception_handler(_: Request, exc: RealSubmitGateBlockedError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "real_submit_gate_blocked", "detail": str(exc), "blocked_by": "real_submit_gate"},
        )

    @app.exception_handler(SafetyBlockedError)
    async def safety_blocked_exception_handler(_: Request, exc: SafetyBlockedError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "safety_blocked", "detail": str(exc), "blocked_by": "safety_engine"},
        )

    # Attach routers
    app.include_router(dry_run_router)
    app.include_router(applications_router)
    app.include_router(ops_router)
    app.include_router(pilot_router)
    app.include_router(dashboard_router)

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Service Health Check",
        description="Returns service health status without disclosing internal paths, keys, or credentials.",
    )
    async def get_health(active_settings: Settings = Depends(get_settings)) -> HealthResponse:
        return HealthResponse(
            status="healthy",
            service="job-agent-api",
            version=active_settings.app_version,
            environment=active_settings.app_env,
        )

    @app.get("/health/live", summary="Liveness Probe")
    async def get_liveness():
        """Kubernetes/Container/Process liveness probe."""
        return {"status": "alive", "service": "job-agent-api"}

    @app.get("/health/ready", summary="Readiness Probe")
    async def get_readiness(active_settings: Settings = Depends(get_settings)):
        """Readiness probe verifying API server and configuration readiness."""
        return {
            "status": "ready",
            "service": "job-agent-api",
            "real_submit_gate_locked": not active_settings.real_submit_gate_enabled,
        }

    return app


app = create_app()
