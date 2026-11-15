"""Operational Metrics Aggregation from Verifiable Persistence (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 13)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from worker.application.models import ApplicationStatus
from worker.application.repository import ApplicationEventRepository, ApplicationRepository
from worker.discovery.repository import JobRepository
from worker.ops.provider_health import ProviderHealthManager


class OperationalMetrics(BaseModel):
    user_id: str
    generated_at: datetime
    jobs_discovered: int = 0
    jobs_matched: int = 0
    jobs_rejected: int = 0
    applications_total: int = 0
    applications_awaiting_approval: int = 0
    applications_needs_user_input: int = 0
    applications_dry_run_done: int = 0
    applications_applied: int = 0
    applications_skipped: int = 0
    applications_failed: int = 0
    applications_uncertain: int = 0
    interrupted_runs_count: int = 0
    provider_health: Dict[str, str] = Field(default_factory=dict)
    field_resolution_summary: Dict[str, int] = Field(default_factory=dict)


class MetricsAggregator:
    """Aggregates truthful operational metrics from stored applications, events, and jobs."""

    def __init__(
        self,
        application_repo: ApplicationRepository,
        event_repo: ApplicationEventRepository,
        job_repo: Optional[JobRepository] = None,
        health_mgr: Optional[ProviderHealthManager] = None,
    ) -> None:
        self.app_repo = application_repo
        self.event_repo = event_repo
        self.job_repo = job_repo
        self.health_mgr = health_mgr

    async def get_user_metrics(self, user_id: UUID) -> OperationalMetrics:
        """Derive real metrics strictly from existing repository data for a given user."""
        apps = await self.app_repo.list_by_user(user_id=user_id, limit=1000)
        now = datetime.now(timezone.utc)

        awaiting = 0
        needs_input = 0
        dry_run_done = 0
        applied = 0
        skipped = 0
        failed = 0
        uncertain = 0
        matched = 0
        rejected = 0

        for a in apps:
            if a.status == ApplicationStatus.AWAITING_APPROVAL:
                awaiting += 1
            elif a.status == ApplicationStatus.NEEDS_USER_INPUT:
                needs_input += 1
            elif a.status == ApplicationStatus.DRY_RUN_DONE:
                dry_run_done += 1
            elif a.status == ApplicationStatus.APPLIED:
                applied += 1
            elif a.status == ApplicationStatus.SKIPPED:
                skipped += 1
            elif a.status == ApplicationStatus.FAILED:
                failed += 1
            elif a.status == ApplicationStatus.UNCERTAIN:
                uncertain += 1
            elif a.status == ApplicationStatus.MATCHED:
                matched += 1
            elif a.status == ApplicationStatus.REJECTED:
                rejected += 1

        # Count total jobs discovered if repository is available
        total_jobs = 0
        if self.job_repo:
            all_jobs = await self.job_repo.list_all()
            total_jobs = len(all_jobs)

        # Count interrupted runs / recovery events across user's applications
        interrupted_count = 0
        for a in apps:
            events = await self.event_repo.list_by_application_id(a.id)
            for ev in events:
                if ev.event_type in ("RECOVERY_INITIATED", "RECOVERY_FAILED"):
                    interrupted_count += 1

        # Provider health map
        provider_health_map: Dict[str, str] = {}
        if self.health_mgr:
            for prov, state in self.health_mgr.get_all_states().items():
                provider_health_map[prov] = state.status.value

        return OperationalMetrics(
            user_id=str(user_id),
            generated_at=now,
            jobs_discovered=total_jobs,
            jobs_matched=matched,
            jobs_rejected=rejected,
            applications_total=len(apps),
            applications_awaiting_approval=awaiting,
            applications_needs_user_input=needs_input,
            applications_dry_run_done=dry_run_done,
            applications_applied=applied,
            applications_skipped=skipped,
            applications_failed=failed,
            applications_uncertain=uncertain,
            interrupted_runs_count=interrupted_count,
            provider_health=provider_health_map,
        )
