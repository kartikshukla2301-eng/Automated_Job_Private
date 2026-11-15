"""Application lifecycle management API routes."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from services.api.dependencies import (
    get_application_event_repository,
    get_application_orchestrator,
    get_application_repository,
    verify_worker_token,
)
from services.api.schemas import (
    ApplicationApprovalRequest,
    ApplicationEventResponse,
    ApplicationRejectionRequest,
    ApplicationResponse,
    GreenhouseDryRunRequest,
    SafetyErrorResponse,
)
from worker.application.exceptions import (
    ApplicationNotFoundError,
    ApprovalRequiredError,
    InvalidStateTransitionError,
    SafetyGateError,
    TerminalStateError,
)
from worker.application.models import Application, ApplicationEvent
from worker.application.orchestrator import ApplicationOrchestrator
from worker.application.repository import (
    ApplicationEventRepository,
    ApplicationRepository,
)
from worker.core.exceptions import (
    CapExceededError,
    KillSwitchActiveError,
    RealSubmitGateBlockedError,
    SafetyBlockedError,
)

logger = logging.getLogger("services.api.routes.applications")

router = APIRouter(
    prefix="/api/v1/applications",
    tags=["Applications"],
    dependencies=[Depends(verify_worker_token)],
)


def _serialize_app(app: Application) -> ApplicationResponse:
    return ApplicationResponse(
        id=app.id,
        user_id=app.user_id,
        job_id=app.job_id,
        platform=app.platform,
        external_id=app.external_id,
        profile_version=app.profile_version,
        autonomy_level=app.autonomy_level.value,
        status=app.status.value,
        score=app.score,
        score_breakdown=app.score_breakdown,
        approval_status=app.approval_status.value if app.approval_status else None,
        approved_at=app.approved_at.isoformat() if app.approved_at else None,
        idempotency_key=app.idempotency_key,
        evidence_ref=app.evidence_ref,
        error=app.error,
        applied_at=app.applied_at.isoformat() if app.applied_at else None,
        created_at=app.created_at.isoformat(),
        updated_at=app.updated_at.isoformat(),
    )


def _serialize_event(ev: ApplicationEvent) -> ApplicationEventResponse:
    return ApplicationEventResponse(
        id=ev.id,
        application_id=ev.application_id,
        event_type=ev.event_type,
        previous_status=ev.previous_status.value if ev.previous_status else None,
        new_status=ev.new_status.value if ev.new_status else None,
        reason=ev.reason,
        triggering_component=ev.triggering_component,
        timestamp=ev.timestamp.isoformat(),
        payload=ev.payload,
    )


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Get Application by ID",
    description="Retrieve an application lifecycle record by its UUID.",
)
async def get_application(
    application_id: UUID,
    repo: ApplicationRepository = Depends(get_application_repository),
) -> ApplicationResponse:
    app = await repo.get_by_id(application_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )
    return _serialize_app(app)


@router.get(
    "/{application_id}/events",
    response_model=List[ApplicationEventResponse],
    summary="Get Application Audit Events",
    description="Retrieve chronological append-only audit trail events for an application.",
)
async def get_application_events(
    application_id: UUID,
    event_repo: ApplicationEventRepository = Depends(get_application_event_repository),
) -> List[ApplicationEventResponse]:
    events = await event_repo.list_by_application_id(application_id)
    return [_serialize_event(e) for e in events]


@router.post(
    "/{application_id}/approve",
    response_model=ApplicationResponse,
    summary="User Approval Gate",
    description="Explicitly approves an application in AWAITING_APPROVAL status, transitioning to FILLING.",
)
async def approve_application(
    application_id: UUID,
    request: ApplicationApprovalRequest,
    orchestrator: ApplicationOrchestrator = Depends(get_application_orchestrator),
) -> ApplicationResponse:
    try:
        updated = await orchestrator.approve(
            application_id=application_id,
            user_id=request.user_id,
        )
        return _serialize_app(updated)
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except (InvalidStateTransitionError, TerminalStateError) as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))


@router.post(
    "/{application_id}/reject",
    response_model=ApplicationResponse,
    summary="User Rejection Gate",
    description="Explicitly rejects an application, transitioning to terminal REJECTED status.",
)
async def reject_application(
    application_id: UUID,
    request: ApplicationRejectionRequest,
    orchestrator: ApplicationOrchestrator = Depends(get_application_orchestrator),
) -> ApplicationResponse:
    try:
        updated = await orchestrator.reject(
            application_id=application_id,
            user_id=request.user_id,
            reason=request.reason,
        )
        return _serialize_app(updated)
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except (InvalidStateTransitionError, TerminalStateError) as err:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(err))


@router.post(
    "/{application_id}/execute-dry-run",
    response_model=ApplicationResponse,
    summary="Execute L0 Dry Run",
    description="Executes safe L0 form inspection and filling for an approved application in FILLING status.",
)
async def execute_dry_run_for_application(
    application_id: UUID,
    request: GreenhouseDryRunRequest,
    user_id: UUID,
    orchestrator: ApplicationOrchestrator = Depends(get_application_orchestrator),
) -> ApplicationResponse:
    try:
        updated = await orchestrator.execute_dry_run(
            application_id=application_id,
            user_id=user_id,
            job_url_or_path="fixtures/forms/greenhouse_job.html",
            company=request.company,
            provider_name="greenhouse",
        )
        return _serialize_app(updated)
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except ApprovalRequiredError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except (KillSwitchActiveError, SafetyBlockedError) as err:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(err))
    except CapExceededError as err:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(err))
