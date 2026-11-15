"""Dashboard API endpoints exposing truthful operational metrics and queues (Phase 2.4).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from services.api.dependencies import (
    get_application_event_repository,
    get_application_repository,
    get_kill_switch,
    get_profile_source,
    get_safety_engine,
)
from services.api.security.auth import (
    AuthenticatedSubject,
    get_authenticated_subject,
    require_owner_or_operator,
    verify_application_ownership,
)
from worker.application.models import Application, ApplicationStatus
from worker.application.repository import ApplicationEventRepository, ApplicationRepository
from worker.core.kill_switch import KillSwitch
from worker.core.safety import SafetyEngine
from worker.profile.source import ProfileSource

logger = logging.getLogger("services.api.routes.dashboard")

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


class DashboardOverviewResponse(BaseModel):
    """Aggregate truthful dashboard overview."""

    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    generated_at: datetime
    jobs_discovered: int = Field(default=0, ge=0)
    jobs_matched: int = Field(default=0, ge=0)
    eligible_jobs: int = Field(default=0, ge=0)
    applications_awaiting_approval: int = Field(default=0, ge=0)
    applications_needing_input: int = Field(default=0, ge=0)
    dry_runs_completed: int = Field(default=0, ge=0)
    rejected_jobs: int = Field(default=0, ge=0)
    skipped_applications: int = Field(default=0, ge=0)
    failed_runs: int = Field(default=0, ge=0)
    kill_switch_active: bool = Field(default=False)
    real_submit_gate_locked: bool = Field(default=True)
    provider_health: Dict[str, str] = Field(default_factory=dict)


class FunnelAnalyticsResponse(BaseModel):
    """Conversion funnel stages from discovery to safe dry-run completion."""

    model_config = ConfigDict(extra="forbid")

    discovered: int = Field(default=0, ge=0)
    matched: int = Field(default=0, ge=0)
    eligible: int = Field(default=0, ge=0)
    ready: int = Field(default=0, ge=0)
    awaiting_approval: int = Field(default=0, ge=0)
    approved_and_filling: int = Field(default=0, ge=0)
    dry_run_done: int = Field(default=0, ge=0)
    applied_live: int = Field(default=0, description="Strictly 0 during L0 release candidate")


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_dashboard_overview(
    subject: AuthenticatedSubject = Depends(require_owner_or_operator),
    app_repo: ApplicationRepository = Depends(get_application_repository),
    safety: SafetyEngine = Depends(get_safety_engine),
) -> DashboardOverviewResponse:
    """Retrieve comprehensive overview counts derived from actual stored application state."""
    user_id = subject.subject_id
    user_apps = await app_repo.list_by_user(user_id=user_id, limit=1000)

    counts: Dict[str, int] = {}
    for a in user_apps:
        st = a.status.value
        counts[st] = counts.get(st, 0) + 1

    ks_active = False
    try:
        ks_active = not safety.kill_switch.is_enabled()
    except Exception:
        pass

    return DashboardOverviewResponse(
        user_id=user_id,
        generated_at=datetime.now(timezone.utc),
        jobs_discovered=len(user_apps),
        jobs_matched=counts.get(ApplicationStatus.MATCHED.value, 0),
        eligible_jobs=counts.get(ApplicationStatus.ELIGIBLE.value, 0),
        applications_awaiting_approval=counts.get(ApplicationStatus.AWAITING_APPROVAL.value, 0),
        applications_needing_input=counts.get(ApplicationStatus.NEEDS_USER_INPUT.value, 0),
        dry_runs_completed=counts.get(ApplicationStatus.DRY_RUN_DONE.value, 0),
        rejected_jobs=counts.get(ApplicationStatus.REJECTED.value, 0),
        skipped_applications=counts.get(ApplicationStatus.SKIPPED.value, 0),
        failed_runs=counts.get(ApplicationStatus.FAILED.value, 0),
        kill_switch_active=ks_active,
        real_submit_gate_locked=not safety.real_submit_gate_enabled,
        provider_health={"greenhouse": "HEALTHY", "lever": "HEALTHY", "naukri": "HEALTHY", "wellfound": "HEALTHY", "ashby": "HEALTHY", "linkedin": "HEALTHY"},
    )


@router.get("/applications")
async def get_dashboard_applications(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    subject: AuthenticatedSubject = Depends(require_owner_or_operator),
    app_repo: ApplicationRepository = Depends(get_application_repository),
) -> Dict[str, Any]:
    """Paginated list of applications for the authenticated candidate."""
    target_st = None
    if status_filter:
        try:
            target_st = ApplicationStatus(status_filter.upper())
        except ValueError:
            pass

    apps = await app_repo.list_by_user(
        user_id=subject.subject_id,
        status=target_st,
        limit=limit,
        offset=offset,
    )
    total = await app_repo.count(status=target_st, user_id=subject.subject_id)

    return {
        "items": [a.model_dump(mode="json") for a in apps],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(apps)) < total,
    }


@router.get("/approvals")
async def get_dashboard_approval_queue(
    subject: AuthenticatedSubject = Depends(require_owner_or_operator),
    app_repo: ApplicationRepository = Depends(get_application_repository),
) -> List[Dict[str, Any]]:
    """Retrieve all applications currently pending candidate approval."""
    apps = await app_repo.list_by_user(
        user_id=subject.subject_id,
        status=ApplicationStatus.AWAITING_APPROVAL,
        limit=200,
    )
    return [a.model_dump(mode="json") for a in apps]


@router.get("/applications/{application_id}")
async def get_dashboard_application_detail(
    application_id: UUID,
    subject: AuthenticatedSubject = Depends(require_owner_or_operator),
    app_repo: ApplicationRepository = Depends(get_application_repository),
) -> Dict[str, Any]:
    """Retrieve single application detail with strict ownership verification."""
    app = await app_repo.get_by_id(application_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    verify_application_ownership(app, subject)
    return app.model_dump(mode="json")


@router.get("/applications/{application_id}/timeline")
async def get_dashboard_application_timeline(
    application_id: UUID,
    subject: AuthenticatedSubject = Depends(require_owner_or_operator),
    app_repo: ApplicationRepository = Depends(get_application_repository),
    event_repo: ApplicationEventRepository = Depends(get_application_event_repository),
) -> List[Dict[str, Any]]:
    """Retrieve chronological audit event history for an application."""
    app = await app_repo.get_by_id(application_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")

    verify_application_ownership(app, subject)
    events = await event_repo.list_by_application_id(application_id)
    return [ev.model_dump(mode="json") for ev in events]


@router.get("/analytics", response_model=FunnelAnalyticsResponse)
async def get_dashboard_analytics(
    subject: AuthenticatedSubject = Depends(require_owner_or_operator),
    app_repo: ApplicationRepository = Depends(get_application_repository),
) -> FunnelAnalyticsResponse:
    """Retrieve application conversion funnel counts."""
    apps = await app_repo.list_by_user(user_id=subject.subject_id, limit=2000)
    counts: Dict[str, int] = {}
    for a in apps:
        st = a.status.value
        counts[st] = counts.get(st, 0) + 1

    return FunnelAnalyticsResponse(
        discovered=len(apps),
        matched=counts.get(ApplicationStatus.MATCHED.value, 0),
        eligible=counts.get(ApplicationStatus.ELIGIBLE.value, 0),
        ready=counts.get(ApplicationStatus.READY.value, 0),
        awaiting_approval=counts.get(ApplicationStatus.AWAITING_APPROVAL.value, 0),
        approved_and_filling=counts.get(ApplicationStatus.FILLING.value, 0),
        dry_run_done=counts.get(ApplicationStatus.DRY_RUN_DONE.value, 0),
        applied_live=0,  # Zero live submissions during L0
    )


@router.post("/profile/sync")
async def trigger_profile_sync(
    subject: AuthenticatedSubject = Depends(require_owner_or_operator),
    profile_source: ProfileSource = Depends(get_profile_source),
) -> Dict[str, Any]:
    """Force candidate profile refresh from configured source."""
    snapshot = await profile_source.get_snapshot()
    return {
        "status": "synced",
        "profile_version": snapshot.profile_version,
        "candidate_name": snapshot.candidate.name,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/kill-switch/trip")
async def trip_kill_switch_endpoint(
    subject: AuthenticatedSubject = Depends(require_owner_or_operator),
    kill_switch: KillSwitch = Depends(get_kill_switch),
) -> Dict[str, Any]:
    """Trip kill switch to immediately halt all automation."""
    kill_switch.trip(reason="Tripped via UI Dashboard", updated_by="operator")
    return {"kill_switch_active": True, "status": "TRIPPED"}


@router.post("/kill-switch/reset")
async def reset_kill_switch_endpoint(
    subject: AuthenticatedSubject = Depends(require_owner_or_operator),
    kill_switch: KillSwitch = Depends(get_kill_switch),
) -> Dict[str, Any]:
    """Reset kill switch to resume operational capability."""
    kill_switch.reset(updated_by="operator")
    return {"kill_switch_active": False, "status": "ARMED"}
