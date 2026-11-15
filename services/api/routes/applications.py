"""Application lifecycle management API routes."""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from services.api.dependencies import (
    get_application_event_repository,
    get_application_orchestrator,
    get_application_repository,
    get_browser_manager,
    get_navigation_guard,
    get_profile_source,
    verify_worker_token,
)
from services.api.schemas import (
    ApplicationApprovalRequest,
    ApplicationEventResponse,
    ApplicationRejectionRequest,
    ApplicationResponse,
    FillPlanResponse,
    FormInspectionRequest,
    GreenhouseDryRunRequest,
    InspectionEvidenceResponse,
    PlannedFieldResponse,
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
from worker.profile.source import ProfileSource
from worker.browser import (
    BrowserManager,
    ExecutionContext,
    FillPlan,
    InspectionEvidence,
    NavigationGuard,
    PrivateNetworkTargetError,
    SessionTimeoutError,
    UnsupportedDestinationError,
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


_fill_plans: dict[UUID, FillPlan] = {}
_evidence_records: dict[UUID, InspectionEvidence] = {}


def _serialize_fill_plan(plan: FillPlan) -> FillPlanResponse:
    return FillPlanResponse(
        plan_id=plan.plan_id,
        session_id=plan.session_id,
        job_id=plan.job_id,
        canonical_url=plan.canonical_url,
        page_title=plan.page_title,
        total_fields=plan.total_fields,
        auto_approved_count=plan.auto_approved_count,
        needs_review_count=plan.needs_review_count,
        blocked_count=plan.blocked_count,
        unresolved_count=plan.unresolved_count,
        is_executable=plan.is_executable(),
        created_at=plan.created_at.isoformat(),
        fields=[
            PlannedFieldResponse(
                field_id=f.field_id,
                label=f.detected_field.label,
                input_type=f.detected_field.input_type,
                required=f.detected_field.required,
                proposed_answer_ref=f.proposed_answer_ref,
                resolution_outcome=f.resolution_outcome.value,
                policy_type=f.policy_type.value,
                field_category=f.field_category.value,
                confidence=f.confidence,
                explanation=f.explanation,
                required_user_action=f.required_user_action,
                is_safe_to_prefill=f.is_safe_to_prefill,
            )
            for f in plan.fields
        ],
    )


def _serialize_evidence(ev: InspectionEvidence) -> InspectionEvidenceResponse:
    return InspectionEvidenceResponse(
        evidence_id=ev.evidence_id,
        session_id=ev.session_id,
        job_id=ev.job_id,
        provider=ev.provider,
        canonical_url=ev.canonical_url,
        page_title=ev.page_title,
        inspection_timestamp=ev.inspection_timestamp.isoformat(),
        detected_field_count=ev.detected_field_count,
        resolved_field_count=ev.resolved_field_count,
        unresolved_field_count=ev.unresolved_field_count,
        blocked_field_count=ev.blocked_field_count,
        outcome=ev.outcome,
        screenshot_path=ev.screenshot_path,
        fill_plan_id=ev.fill_plan_id,
        errors=ev.errors,
    )


@router.post(
    "/{application_id}/inspect-form",
    response_model=FillPlanResponse,
    summary="Inspect Application Form (L0)",
    description="Inspects an application form safely and produces an explainable FillPlan without entering data.",
)
async def inspect_application_form(
    application_id: UUID,
    request: FormInspectionRequest,
    repo: ApplicationRepository = Depends(get_application_repository),
    browser_manager: BrowserManager = Depends(get_browser_manager),
    navigation_guard: NavigationGuard = Depends(get_navigation_guard),
    profile_source: ProfileSource = Depends(get_profile_source),
) -> FillPlanResponse:
    app = await repo.get_by_id(application_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )
    if app.user_id != request.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Application does not belong to specified user.",
        )

    target_url = request.job_url_or_path or "fixtures/forms/greenhouse_job.html"
    profile = await profile_source.get_snapshot()
    session = await browser_manager.create_session(user_id=request.user_id)

    try:
        ctx = ExecutionContext(
            session=session,
            navigation_guard=navigation_guard,
            profile=profile,
        )
        plan, evidence = await ctx.inspect_and_plan(
            target_url=target_url,
            provider_name=request.provider_name,
            job_id=app.job_id,
        )
        _fill_plans[application_id] = plan
        _evidence_records[application_id] = evidence
        return _serialize_fill_plan(plan)
    except (UnsupportedDestinationError, PrivateNetworkTargetError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except SessionTimeoutError as err:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(err))
    except Exception as err:
        logger.exception("Form inspection failed for application %s: %s", application_id, err)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Inspection failed: {err}")
    finally:
        await session.close()


@router.get(
    "/{application_id}/fill-plan",
    response_model=FillPlanResponse,
    summary="Get Application Fill Plan",
    description="Retrieve the latest inspectable FillPlan for an application.",
)
async def get_application_fill_plan(
    application_id: UUID,
    repo: ApplicationRepository = Depends(get_application_repository),
) -> FillPlanResponse:
    app = await repo.get_by_id(application_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )

    plan = _fill_plans.get(application_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No FillPlan found for application '{application_id}'. Run inspection first.",
        )
    return _serialize_fill_plan(plan)


@router.get(
    "/{application_id}/evidence",
    response_model=InspectionEvidenceResponse,
    summary="Get Application Inspection Evidence",
    description="Retrieve evidence metadata and screenshot reference for an application inspection.",
)
async def get_application_evidence(
    application_id: UUID,
    repo: ApplicationRepository = Depends(get_application_repository),
) -> InspectionEvidenceResponse:
    app = await repo.get_by_id(application_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )

    ev = _evidence_records.get(application_id)
    if not ev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No inspection evidence found for application '{application_id}'.",
        )
    return _serialize_evidence(ev)


from worker.application.outcomes import (
    ApplicationOutcomeRecord,
    OutcomeMilestone,
    OutcomeTracker,
)
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class RecordOutcomeRequest(BaseModel):
    milestone: OutcomeMilestone
    event_timestamp: Optional[datetime] = None
    notes: Optional[str] = None
    recruiter_contact: Optional[str] = None
    offer_amount: Optional[float] = None


_outcome_tracker = OutcomeTracker()


@router.post(
    "/{application_id}/outcomes",
    response_model=ApplicationOutcomeRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record Application Outcome Milestone",
    description="Record an interview, offer, or post-application decision milestone.",
)
async def record_application_outcome(
    application_id: UUID,
    request: RecordOutcomeRequest,
    repo: ApplicationRepository = Depends(get_application_repository),
) -> ApplicationOutcomeRecord:
    app = await repo.get_by_id(application_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )

    record = _outcome_tracker.record_milestone(
        application_id=str(application_id),
        milestone=request.milestone,
        event_timestamp=request.event_timestamp,
        notes=request.notes,
        recruiter_contact=request.recruiter_contact,
        offer_amount=request.offer_amount,
    )
    return record


@router.get(
    "/{application_id}/outcomes",
    response_model=List[ApplicationOutcomeRecord],
    summary="List Application Outcome Milestones",
    description="Retrieve all interview, offer, and decision milestones recorded for an application.",
)
async def get_application_outcomes(
    application_id: UUID,
    repo: ApplicationRepository = Depends(get_application_repository),
) -> List[ApplicationOutcomeRecord]:
    app = await repo.get_by_id(application_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application '{application_id}' not found.",
        )

    return _outcome_tracker.get_outcomes_for_application(str(application_id))
