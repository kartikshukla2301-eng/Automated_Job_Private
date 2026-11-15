"""Operational Control Plane API routes (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12, 13)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from services.api.dependencies import (
    get_approval_manager,
    get_canary_runner,
    get_heartbeat_manager,
    get_metrics_aggregator,
    get_provider_health_manager,
    get_readiness_evaluator,
    get_telegram_service,
    verify_worker_token,
)
from services.api.schemas import (
    ApplicationResponse,
    HeartbeatResponse,
    ProviderHealthResponse,
    ReadinessReportResponse,
    ResolveUserInputRequest,
    TelegramCommandResponse,
    TelegramWebhookRequest,
)
from worker.application.exceptions import (
    ApplicationNotFoundError,
    TerminalStateError,
)
from worker.ops.approval import (
    ApprovalAuthorizationError,
    ApprovalExpiredError,
    ApprovalManager,
    ApprovalStateError,
)
from worker.ops.canary import CanaryResult, ProviderCanaryRunner
from worker.ops.heartbeat import HeartbeatManager
from worker.ops.metrics import MetricsAggregator
from worker.ops.provider_health import ProviderHealthManager
from worker.ops.readiness import RealSubmitReadinessEvaluator
from worker.ops.telegram import TelegramNotificationService, TelegramSecurityError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/ops",
    tags=["operations"],
    dependencies=[Depends(verify_worker_token)],
)


def _serialize_app(app: Any) -> ApplicationResponse:
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


@router.get(
    "/approvals",
    response_model=List[ApplicationResponse],
    summary="Get User Approval Queue",
    description="Retrieve all applications queued in AWAITING_APPROVAL for the specified user.",
)
async def get_approval_queue(
    user_id: UUID = Query(..., description="Target user UUID"),
    approval_mgr: ApprovalManager = Depends(get_approval_manager),
) -> List[ApplicationResponse]:
    apps = await approval_mgr.get_approval_queue(user_id=user_id)
    return [_serialize_app(a) for a in apps]


@router.post(
    "/approvals/{application_id}/resolve-input",
    response_model=ApplicationResponse,
    summary="Resolve Candidate Missing Input",
    description="Provide missing answers for an application in NEEDS_USER_INPUT and requeue it for approval.",
)
async def resolve_user_input(
    application_id: UUID,
    request: ResolveUserInputRequest,
    approval_mgr: ApprovalManager = Depends(get_approval_manager),
) -> ApplicationResponse:
    try:
        updated = await approval_mgr.resolve_user_input(
            application_id=application_id,
            user_id=request.user_id,
            provided_answers=request.answers,
        )
        return _serialize_app(updated)
    except ApplicationNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except ApprovalAuthorizationError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ApprovalStateError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get(
    "/provider-health",
    response_model=List[ProviderHealthResponse],
    summary="List Provider Health States",
    description="Retrieve health metrics and paused status for all monitored job board providers.",
)
async def get_provider_health(
    health_mgr: ProviderHealthManager = Depends(get_provider_health_manager),
) -> List[ProviderHealthResponse]:
    states = health_mgr.get_all_states()
    return [
        ProviderHealthResponse(
            provider_name=s.provider_name,
            status=s.status.value,
            consecutive_failures=s.consecutive_failures,
            successful_inspections=s.successful_inspections,
            navigation_failures=s.navigation_failures,
            selector_failures=s.selector_failures,
            browser_crashes=s.browser_crashes,
            timeouts=s.timeouts,
            last_failure_reason=s.last_failure_reason,
            pause_reason=s.pause_reason,
        )
        for s in states.values()
    ]


@router.post(
    "/provider-health/{provider}/pause",
    response_model=ProviderHealthResponse,
    summary="Manually Pause Provider",
    description="Immediately pause a job board provider to prevent further automated execution.",
)
async def pause_provider(
    provider: str,
    health_mgr: ProviderHealthManager = Depends(get_provider_health_manager),
) -> ProviderHealthResponse:
    s = health_mgr.pause_provider(provider, reason="Operator API call")
    return ProviderHealthResponse(
        provider_name=s.provider_name,
        status=s.status.value,
        consecutive_failures=s.consecutive_failures,
        successful_inspections=s.successful_inspections,
        navigation_failures=s.navigation_failures,
        selector_failures=s.selector_failures,
        browser_crashes=s.browser_crashes,
        timeouts=s.timeouts,
        last_failure_reason=s.last_failure_reason,
        pause_reason=s.pause_reason,
    )


@router.post(
    "/provider-health/{provider}/resume",
    response_model=ProviderHealthResponse,
    summary="Manually Resume Provider",
    description="Resume a paused job board provider and reset failure counters.",
)
async def resume_provider(
    provider: str,
    health_mgr: ProviderHealthManager = Depends(get_provider_health_manager),
) -> ProviderHealthResponse:
    s = health_mgr.resume_provider(provider)
    return ProviderHealthResponse(
        provider_name=s.provider_name,
        status=s.status.value,
        consecutive_failures=s.consecutive_failures,
        successful_inspections=s.successful_inspections,
        navigation_failures=s.navigation_failures,
        selector_failures=s.selector_failures,
        browser_crashes=s.browser_crashes,
        timeouts=s.timeouts,
        last_failure_reason=s.last_failure_reason,
        pause_reason=s.pause_reason,
    )


@router.get(
    "/heartbeat",
    response_model=HeartbeatResponse,
    summary="Get Worker Heartbeat Status",
    description="Retrieve worker heartbeat status, dead-man status, and last active timestamp.",
)
async def get_heartbeat(
    heartbeat_mgr: HeartbeatManager = Depends(get_heartbeat_manager),
) -> HeartbeatResponse:
    state = heartbeat_mgr.check_health()
    return HeartbeatResponse(
        worker_id=state.worker_id,
        status=state.status.value,
        last_heartbeat=state.last_heartbeat.isoformat(),
        last_successful_run=state.last_successful_run.isoformat() if state.last_successful_run else None,
        total_runs_completed=state.total_runs_completed,
    )


@router.post(
    "/heartbeat/pulse",
    response_model=HeartbeatResponse,
    summary="Emit Worker Heartbeat Pulse",
    description="Worker process emits a periodic heartbeat signal.",
)
async def pulse_heartbeat(
    heartbeat_mgr: HeartbeatManager = Depends(get_heartbeat_manager),
) -> HeartbeatResponse:
    state = heartbeat_mgr.pulse()
    return HeartbeatResponse(
        worker_id=state.worker_id,
        status=state.status.value,
        last_heartbeat=state.last_heartbeat.isoformat(),
        last_successful_run=state.last_successful_run.isoformat() if state.last_successful_run else None,
        total_runs_completed=state.total_runs_completed,
    )


@router.post(
    "/canaries/{provider}/run",
    response_model=CanaryResult,
    summary="Run Provider Canary",
    description="Executes a safe offline canary inspection against approved test fixtures to detect form drift.",
)
async def run_canary(
    provider: str,
    canary_runner: ProviderCanaryRunner = Depends(get_canary_runner),
) -> CanaryResult:
    return await canary_runner.run_canary(provider)


@router.get(
    "/metrics",
    summary="Get Operational Metrics",
    description="Retrieve aggregated operational metrics strictly derived from stored records for the user.",
)
async def get_metrics(
    user_id: UUID = Query(..., description="Target user UUID"),
    metrics_aggregator: MetricsAggregator = Depends(get_metrics_aggregator),
) -> Dict[str, Any]:
    metrics = await metrics_aggregator.get_user_metrics(user_id=user_id)
    return metrics.model_dump()


@router.get(
    "/readiness",
    response_model=ReadinessReportResponse,
    summary="Evaluate Real-Submit Readiness",
    description="Non-executable evaluation of the 8 locked architecture gate criteria. Informational only.",
)
async def get_readiness_report(
    evaluator: RealSubmitReadinessEvaluator = Depends(get_readiness_evaluator),
) -> ReadinessReportResponse:
    report = evaluator.evaluate()
    return ReadinessReportResponse(
        generated_at=report.generated_at.isoformat(),
        overall_status=report.overall_status.value,
        real_submit_gate_enabled=report.real_submit_gate_enabled,
        summary=report.summary,
        criteria=[c.model_dump() for c in report.criteria],
    )


@router.post(
    "/telegram/webhook",
    response_model=TelegramCommandResponse,
    summary="Telegram Owner Command Webhook",
    description="Processes inbound Telegram bot commands from authenticated owner chat IDs.",
)
async def handle_telegram_webhook(
    request: TelegramWebhookRequest,
    telegram_svc: TelegramNotificationService = Depends(get_telegram_service),
) -> TelegramCommandResponse:
    try:
        resp_text = await telegram_svc.handle_command(
            chat_id=request.chat_id,
            command_text=request.command_text,
            user_id=request.user_id,
        )
        return TelegramCommandResponse(success=True, response_text=resp_text)
    except TelegramSecurityError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except Exception as err:
        logger.exception("Error processing Telegram command: %s", err)
        return TelegramCommandResponse(success=False, response_text=f"Command execution error: {err}")
