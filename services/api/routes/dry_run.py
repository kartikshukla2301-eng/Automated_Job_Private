"""Dry-run execution API routes."""

import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from services.api.dependencies import get_walking_skeleton_workflow, verify_worker_token
from services.api.schemas import (
    GreenhouseDryRunRequest,
    GreenhouseDryRunResponse,
    SafetyErrorResponse,
)
from worker.core.exceptions import (
    CapExceededError,
    InvalidSafetyStateError,
    KillSwitchActiveError,
    RealSubmitGateBlockedError,
    SafetyBlockedError,
)
from worker.core.runner import DryRunExecutionResult
from worker.core.workflow import WalkingSkeletonWorkflow

logger = logging.getLogger("services.api.routes.dry_run")

router = APIRouter(
    prefix="/api/v1/dry-run",
    tags=["Dry Run"],
    dependencies=[Depends(verify_worker_token)],
)


def _sanitize_path(path_str: Optional[str]) -> Optional[str]:
    """Convert local filesystem path to a safe relative reference, avoiding host leakage."""
    if not path_str:
        return None
    p = Path(path_str)
    try:
        return str(p.relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        return f"evidence/{p.name}" if "evidence" in p.parts else p.name


@router.post(
    "/greenhouse",
    response_model=GreenhouseDryRunResponse,
    responses={
        400: {"model": SafetyErrorResponse, "description": "Validation or execution error"},
        401: {"description": "Missing or invalid worker token"},
        403: {"model": SafetyErrorResponse, "description": "Blocked by pre-application safety barrier"},
        423: {"model": SafetyErrorResponse, "description": "Blocked by active kill switch"},
        429: {"model": SafetyErrorResponse, "description": "Blocked by application caps"},
        500: {"model": SafetyErrorResponse, "description": "Invalid safety state (fail closed)"},
    },
    summary="Execute Greenhouse Dry-Run Walking Skeleton",
    description=(
        "Executes a deterministic, safe dry-run application against the approved local "
        "Greenhouse HTML fixture. Does NOT accept arbitrary URLs or external paths. "
        "Enforces pre-apply safety barrier before browser navigation, fills only truthful "
        "identity fields, skips sensitive/unknown fields, captures screenshot evidence, "
        "and never submits."
    ),
)
async def execute_greenhouse_dry_run(
    request: GreenhouseDryRunRequest = GreenhouseDryRunRequest(),
    workflow: WalkingSkeletonWorkflow = Depends(get_walking_skeleton_workflow),
) -> GreenhouseDryRunResponse:
    try:
        result: DryRunExecutionResult = await workflow.run_greenhouse_dry_run(
            company=request.company,
        )
    except KillSwitchActiveError as exc:
        logger.warning("Dry-run blocked by active kill switch: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_423_LOCKED,
            content={"error": "kill_switch_active", "detail": str(exc), "blocked_by": "kill_switch"},
        )
    except CapExceededError as exc:
        logger.warning("Dry-run blocked by application caps: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "cap_exceeded", "detail": str(exc), "blocked_by": "application_caps"},
        )
    except InvalidSafetyStateError as exc:
        logger.error("Dry-run failed closed due to invalid safety state: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "invalid_safety_state",
                "detail": "Safety system state is uninitialized or invalid. Automation halted fail-closed.",
                "blocked_by": "invalid_safety_state",
            },
        )
    except RealSubmitGateBlockedError as exc:
        logger.error("Real submit gate blocked in dry-run route: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "real_submit_gate_blocked", "detail": str(exc), "blocked_by": "real_submit_gate"},
        )
    except SafetyBlockedError as exc:
        logger.warning("Dry-run blocked by safety barrier: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "safety_blocked", "detail": str(exc), "blocked_by": "safety_engine"},
        )
    except FileNotFoundError as exc:
        logger.error("Resource not found during dry-run: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "resource_not_found",
                "detail": "Requested job fixture or required local resource was not found.",
                "blocked_by": "filesystem",
            },
        )
    except ValueError as exc:
        logger.warning("Invalid argument during dry-run: %s", exc)
        msg = str(exc)
        safe_detail = (
            "Invalid request parameters or disallowed fixture path navigation."
            if any(ch in msg for ch in ("\\", "/", ":", "outside approved directory"))
            else msg
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "bad_request", "detail": safe_detail, "blocked_by": "validation"},
        )

    safe_job_url = _sanitize_path(result.job_url) or "fixtures/forms/greenhouse_job.html"
    safe_screenshot_path = _sanitize_path(result.screenshot_path)

    return GreenhouseDryRunResponse(
        job_url=safe_job_url,
        company=result.company,
        provider=result.provider,
        profile_version=result.profile_version,
        fields_filled=result.fields_filled,
        unresolved_fields=result.unresolved_fields,
        screenshot_path=safe_screenshot_path,
        status=result.status,
        executed_at=result.executed_at.isoformat(),
        safety_allowed=result.safety_decision.allowed if result.safety_decision else True,
        safety_reason=result.safety_decision.reason if result.safety_decision else "Safety checks passed",
    )
