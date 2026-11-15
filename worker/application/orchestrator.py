"""Central Application Orchestrator managing end-to-end application lifecycle.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 13, 14, 15)
- docs/BUILD_RULES.md
- docs/DECISIONS.md (AD-005, AD-006, AD-007, AD-008, AD-009)

LIFECYCLE PIPELINE (L0):
DISCOVERED -> MATCHED -> ELIGIBLE -> READY -> AWAITING_APPROVAL -> FILLING -> DRY_RUN_DONE
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from worker.application.exceptions import (
    ApplicationNotFoundError,
    ApprovalRequiredError,
    SafetyGateError,
)
from worker.application.idempotency import generate_application_idempotency_key
from worker.application.models import (
    Application,
    ApplicationEvent,
    ApplicationEventType,
    ApplicationStatus,
    ApprovalStatus,
    AutonomyLevel,
)
from worker.application.repository import (
    ApplicationEventRepository,
    ApplicationRepository,
)
from worker.application.state_machine import ApplicationStateMachine
from worker.core.exceptions import SafetyBlockedError
from worker.core.runner import DryRunExecutionResult, JobApplicationRunner
from worker.core.safety import SafetyEngine
from worker.discovery.models import Job
from worker.matching.models import CandidateJobPreferences, JobMatchRequest, MatchDecision
from worker.matching.service import JobMatchingService
from worker.profile.models import ProfileSnapshot

logger = logging.getLogger("worker.application.orchestrator")


class ApplicationOrchestrator:
    """Central orchestrator coordinating discovery, matching, policy, safety, and application lifecycle."""

    def __init__(
        self,
        application_repo: ApplicationRepository,
        event_repo: ApplicationEventRepository,
        matching_service: JobMatchingService,
        safety_engine: SafetyEngine,
        runner: JobApplicationRunner,
        state_machine: Optional[ApplicationStateMachine] = None,
    ) -> None:
        self.application_repo = application_repo
        self.event_repo = event_repo
        self.matching_service = matching_service
        self.safety_engine = safety_engine
        self.runner = runner
        self.state_machine = state_machine or ApplicationStateMachine()

    async def create_or_get_application(
        self,
        user_id: UUID,
        job: Job,
        profile_snapshot: ProfileSnapshot,
        autonomy_level: AutonomyLevel = AutonomyLevel.L0,
        run_id: Optional[UUID] = None,
    ) -> Tuple[Application, bool]:
        """Create a new Application in DISCOVERED status, or idempotently return existing.

        Returns (application, created_flag).
        """
        existing = await self.application_repo.get_by_user_and_job(user_id=user_id, job_id=job.id)
        if existing:
            return existing, False

        idempotency_key = generate_application_idempotency_key(
            user_id=user_id,
            job_id=job.id,
            profile_version=profile_snapshot.profile_version,
        )

        # Check by idempotency key
        existing_idmp = await self.application_repo.get_by_idempotency_key(idempotency_key)
        if existing_idmp:
            return existing_idmp, False

        now = datetime.now(timezone.utc)
        app = Application(
            user_id=user_id,
            job_id=job.id,
            platform=job.platform,
            external_id=job.external_id,
            profile_version=profile_snapshot.profile_version,
            autonomy_level=autonomy_level,
            status=ApplicationStatus.DISCOVERED,
            idempotency_key=idempotency_key,
            run_id=run_id,
            created_at=now,
            updated_at=now,
        )

        created_app = await self.application_repo.create(app)

        event = ApplicationEvent(
            application_id=created_app.id,
            event_type=ApplicationEventType.CREATED.value,
            previous_status=None,
            new_status=ApplicationStatus.DISCOVERED,
            reason="Application record created from discovered job",
            triggering_component="ApplicationOrchestrator",
            run_id=run_id,
            payload={
                "platform": job.platform,
                "external_id": job.external_id,
                "company": job.company,
                "title": job.title,
            },
            timestamp=now,
        )
        await self.event_repo.append_event(event)
        return created_app, True

    async def evaluate_matching(
        self,
        application_id: UUID,
        job: Job,
        profile_snapshot: ProfileSnapshot,
        preferences: Optional[CandidateJobPreferences] = None,
        run_id: Optional[UUID] = None,
    ) -> Application:
        """Evaluate candidate-job fit and transition DISCOVERED -> MATCHED or REJECTED."""
        app = await self._require_application(application_id)

        match_req = JobMatchRequest(
            job=job,
            profile=profile_snapshot,
            preferences=preferences,
            allow_borderline_llm=True,
        )

        match_res = await self.matching_service.match_job(match_req)

        if match_res.decision == MatchDecision.MATCH:
            target_status = ApplicationStatus.MATCHED
            reason = f"Job passed matching criteria with score {match_res.score:.1f}"
        elif match_res.decision == MatchDecision.EXCLUDED:
            target_status = ApplicationStatus.REJECTED
            reason = f"Job excluded by hard filter: {'; '.join(match_res.hard_filter_reasons)}"
        else:
            target_status = ApplicationStatus.REJECTED
            reason = f"Job below matching score threshold ({match_res.score:.1f})"

        updated_app, event = self.state_machine.transition(
            application=app,
            target_status=target_status,
            reason=reason,
            triggering_component="JobMatchingService",
            run_id=run_id,
            payload={
                "score": match_res.score,
                "decision": match_res.decision.value,
                "passed_hard_filters": match_res.passed_hard_filters,
                "breakdown": match_res.breakdown.model_dump(),
            },
        )

        updated_app = updated_app.model_copy(
            update={
                "score": match_res.score,
                "score_breakdown": match_res.breakdown.model_dump(),
            }
        )

        await self.application_repo.update(updated_app)
        await self.event_repo.append_event(event)
        return updated_app

    async def verify_eligibility(
        self,
        application_id: UUID,
        provider_name: str,
        company: str,
        run_id: Optional[UUID] = None,
    ) -> Application:
        """Verify pre-apply safety barrier and transition MATCHED -> ELIGIBLE -> READY -> AWAITING_APPROVAL."""
        app = await self._require_application(application_id)

        try:
            # Enforce pre-apply safety barrier (kill switch, daily caps, company cooldown)
            self.safety_engine.verify_pre_apply(
                company=company,
                provider=provider_name,
            )

            # Transition MATCHED -> ELIGIBLE
            eligible_app, event_eligible = self.state_machine.transition(
                application=app,
                target_status=ApplicationStatus.ELIGIBLE,
                reason="Pre-apply safety checks verified",
                triggering_component="SafetyEngine",
                run_id=run_id,
            )
            await self.application_repo.update(eligible_app)
            await self.event_repo.append_event(event_eligible)

            # Transition ELIGIBLE -> READY
            ready_app, event_ready = self.state_machine.transition(
                application=eligible_app,
                target_status=ApplicationStatus.READY,
                reason="Application staged and ready for execution queue",
                triggering_component="ApplicationOrchestrator",
                run_id=run_id,
            )
            await self.application_repo.update(ready_app)
            await self.event_repo.append_event(event_ready)

            # Transition READY -> AWAITING_APPROVAL (L0 human-in-the-loop requirement)
            awaiting_app, event_awaiting = self.state_machine.transition(
                application=ready_app,
                target_status=ApplicationStatus.AWAITING_APPROVAL,
                reason="Waiting for user review/approval before dry-run execution",
                triggering_component="ApplicationOrchestrator",
                run_id=run_id,
            )
            awaiting_app = awaiting_app.model_copy(
                update={"approval_status": ApprovalStatus.PENDING}
            )
            await self.application_repo.update(awaiting_app)
            await self.event_repo.append_event(event_awaiting)
            return awaiting_app

        except SafetyBlockedError as err:
            updated_app, event = self.state_machine.transition(
                application=app,
                target_status=ApplicationStatus.BLOCKED,
                reason=str(err),
                triggering_component="SafetyEngine",
                run_id=run_id,
                payload={"error": str(err)},
            )
            await self.application_repo.update(updated_app)
            await self.event_repo.append_event(event)
            return updated_app

    async def approve(
        self,
        application_id: UUID,
        user_id: UUID,
        run_id: Optional[UUID] = None,
    ) -> Application:
        """User explicitly approves an application: transitions AWAITING_APPROVAL -> FILLING."""
        app = await self._require_application(application_id)
        if app.user_id != user_id:
            raise ApplicationNotFoundError(f"Application '{application_id}' does not belong to user '{user_id}'.")

        now = datetime.now(timezone.utc)
        filling_app, event = self.state_machine.transition(
            application=app,
            target_status=ApplicationStatus.FILLING,
            reason="User explicitly approved application execution",
            triggering_component="UserApprovalGate",
            run_id=run_id,
        )

        filling_app = filling_app.model_copy(
            update={
                "approval_status": ApprovalStatus.APPROVED,
                "approved_at": now,
            }
        )

        await self.application_repo.update(filling_app)
        await self.event_repo.append_event(event)
        return filling_app

    async def reject(
        self,
        application_id: UUID,
        user_id: UUID,
        reason: str = "Rejected by user",
        run_id: Optional[UUID] = None,
    ) -> Application:
        """User rejects application: transitions to REJECTED."""
        app = await self._require_application(application_id)
        if app.user_id != user_id:
            raise ApplicationNotFoundError(f"Application '{application_id}' does not belong to user '{user_id}'.")

        rejected_app, event = self.state_machine.transition(
            application=app,
            target_status=ApplicationStatus.REJECTED,
            reason=reason,
            triggering_component="UserApprovalGate",
            run_id=run_id,
        )

        rejected_app = rejected_app.model_copy(
            update={"approval_status": ApprovalStatus.REJECTED}
        )

        await self.application_repo.update(rejected_app)
        await self.event_repo.append_event(event)
        return rejected_app

    async def execute_dry_run(
        self,
        application_id: UUID,
        user_id: UUID,
        job_url_or_path: str,
        company: str,
        provider_name: str = "greenhouse",
        page: Optional[Any] = None,
        run_id: Optional[UUID] = None,
    ) -> Application:
        """Execute safe L0 dry-run: fills form in inspection mode, transitions FILLING -> DRY_RUN_DONE.

        CRITICAL SAFETY RULES:
        - NEVER enters real candidate data into external live forms.
        - NEVER clicks submit, apply, or dispatch.
        - NEVER transitions to SUBMITTING or APPLIED in L0.
        """
        app = await self._require_application(application_id)
        if app.user_id != user_id:
            raise ApplicationNotFoundError(f"Application '{application_id}' does not belong to user '{user_id}'.")

        if app.status != ApplicationStatus.FILLING:
            raise ApprovalRequiredError(str(application_id), app.status.value)

        # Log start of dry-run
        start_event = ApplicationEvent(
            application_id=app.id,
            event_type=ApplicationEventType.DRY_RUN_STARTED.value,
            previous_status=app.status,
            new_status=app.status,
            reason="Starting safe L0 dry-run form inspection and fill plan",
            triggering_component="JobApplicationRunner",
            run_id=run_id or app.run_id,
        )
        await self.event_repo.append_event(start_event)

        try:
            dry_run_res: DryRunExecutionResult = await self.runner.execute_dry_run(
                job_url_or_path=job_url_or_path,
                company=company,
                provider_name=provider_name,
                page=page,
            )

            # Check if execution flagged that user input is required
            if dry_run_res.status == "NEEDS_USER_INPUT":
                input_app, event_input = self.state_machine.transition(
                    application=app,
                    target_status=ApplicationStatus.NEEDS_USER_INPUT,
                    reason="Required form fields could not be resolved from Answer Bank or Profile",
                    triggering_component="JobApplicationRunner",
                    run_id=run_id,
                    evidence_ref=dry_run_res.screenshot_path,
                    payload={"unresolved_fields": list(dry_run_res.unresolved_fields)},
                )
                await self.application_repo.update(input_app)
                await self.event_repo.append_event(event_input)
                return input_app

            # Transition FILLING -> DRY_RUN_DONE (L0 terminal state)
            completed_app, event_done = self.state_machine.transition(
                application=app,
                target_status=ApplicationStatus.DRY_RUN_DONE,
                reason="Safe L0 dry-run completed successfully without external submission",
                triggering_component="JobApplicationRunner",
                run_id=run_id,
                evidence_ref=dry_run_res.screenshot_path,
                payload={
                    "fields_filled_count": len(dry_run_res.fields_filled),
                    "unresolved_fields_count": len(dry_run_res.unresolved_fields),
                },
            )

            completed_app = completed_app.model_copy(
                update={
                    "fields_filled": {k: "<RESOLVED_FIELD>" for k in dry_run_res.fields_filled.keys()},
                    "evidence_ref": dry_run_res.screenshot_path,
                }
            )

            await self.application_repo.update(completed_app)
            await self.event_repo.append_event(event_done)
            return completed_app

        except SafetyBlockedError as err:
            blocked_app, event_blocked = self.state_machine.transition(
                application=app,
                target_status=ApplicationStatus.BLOCKED,
                reason=f"Blocked during execution: {err}",
                triggering_component="SafetyEngine",
                run_id=run_id,
                error=str(err),
            )
            await self.application_repo.update(blocked_app)
            await self.event_repo.append_event(event_blocked)
            return blocked_app

        except Exception as err:
            logger.exception("Dry run execution failed for application %s: %s", app.id, err)
            failed_app, event_failed = self.state_machine.transition(
                application=app,
                target_status=ApplicationStatus.FAILED,
                reason=f"Dry run failure: {err}",
                triggering_component="JobApplicationRunner",
                run_id=run_id,
                error=str(err),
            )
            await self.application_repo.update(failed_app)
            await self.event_repo.append_event(event_failed)
            return failed_app

    async def recover_interrupted_application(
        self,
        application_id: UUID,
        reason: str = "Worker process restarted while application was in progress",
    ) -> Application:
        """Safely recover an application that was interrupted while in FILLING.

        CRITICAL ARCHITECTURAL RULES (RC-3):
        - Never blindly replay submission or execution actions.
        - In dry-run, an interrupted FILLING state transitions safely to FAILED (with manual retry allowed).
        """
        app = await self._require_application(application_id)

        recovery_init_event = ApplicationEvent(
            application_id=app.id,
            event_type=ApplicationEventType.RECOVERY_INITIATED.value,
            previous_status=app.status,
            new_status=app.status,
            reason=reason,
            triggering_component="RecoveryEngine",
        )
        await self.event_repo.append_event(recovery_init_event)

        if app.status == ApplicationStatus.FILLING:
            # Transition to FAILED so user/worker can safely review and restart
            failed_app, event_failed = self.state_machine.transition(
                application=app,
                target_status=ApplicationStatus.FAILED,
                reason=f"Interrupted during form filling: {reason}. Manual retry available.",
                triggering_component="RecoveryEngine",
                error=reason,
            )
            await self.application_repo.update(failed_app)
            await self.event_repo.append_event(event_failed)
            return failed_app

        if app.status == ApplicationStatus.SUBMITTING:
            # RC-3: An interrupted real submission becomes UNCERTAIN
            uncertain_app, event_unc = self.state_machine.transition(
                application=app,
                target_status=ApplicationStatus.UNCERTAIN,
                reason="Worker crashed during SUBMITTING; outcome must be verified on platform.",
                triggering_component="RecoveryEngine",
                error=reason,
            )
            await self.application_repo.update(uncertain_app)
            await self.event_repo.append_event(event_unc)
            return uncertain_app

        return app

    async def _require_application(self, application_id: UUID) -> Application:
        app = await self.application_repo.get_by_id(application_id)
        if not app:
            raise ApplicationNotFoundError(str(application_id))
        return app
