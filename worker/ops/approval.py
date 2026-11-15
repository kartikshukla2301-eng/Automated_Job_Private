"""Human-in-the-loop Approval & User-Input Workflow Manager (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 13)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from worker.application.exceptions import (
    ApplicationNotFoundError,
    ApprovalRequiredError,
    InvalidStateTransitionError,
    TerminalStateError,
)
from worker.application.models import (
    Application,
    ApplicationEvent,
    ApplicationEventType,
    ApplicationStatus,
    ApprovalStatus,
)
from worker.application.orchestrator import ApplicationOrchestrator
from worker.application.repository import ApplicationEventRepository, ApplicationRepository

logger = logging.getLogger(__name__)


class ApprovalExpiredError(Exception):
    """Raised when an approval is attempted on an expired application."""


class ApprovalAuthorizationError(Exception):
    """Raised when an unauthorized user attempts an approval operation."""


class ApprovalStateError(Exception):
    """Raised when an approval is attempted in an invalid application state."""


class ApprovalManager:
    """Manages the operational human-in-the-loop approval and user-input queue."""

    def __init__(
        self,
        orchestrator: ApplicationOrchestrator,
        application_repo: ApplicationRepository,
        event_repo: ApplicationEventRepository,
        default_ttl_hours: float = 24.0,
    ) -> None:
        self.orchestrator = orchestrator
        self.application_repo = application_repo
        self.event_repo = event_repo
        self.default_ttl_hours = default_ttl_hours

    async def get_approval_queue(self, user_id: UUID) -> List[Application]:
        """Retrieve all applications currently awaiting user approval for a specific user."""
        all_apps = await self.application_repo.list_by_user(user_id=user_id)
        # Filter for AWAITING_APPROVAL
        queue: List[Application] = []
        now = datetime.now(timezone.utc)
        for app in all_apps:
            if app.status == ApplicationStatus.AWAITING_APPROVAL:
                # Check for stale / expired status on the fly
                age = now - app.updated_at
                if age > timedelta(hours=self.default_ttl_hours):
                    await self._expire_application(app, reason=f"Approval expired after {self.default_ttl_hours}h without user action")
                else:
                    queue.append(app)
        return queue

    async def get_needs_input_queue(self, user_id: UUID) -> List[Application]:
        """Retrieve all applications requiring candidate answers for a specific user."""
        all_apps = await self.application_repo.list_by_user(user_id=user_id)
        return [app for app in all_apps if app.status == ApplicationStatus.NEEDS_USER_INPUT]

    async def approve_application(
        self,
        application_id: UUID,
        user_id: UUID,
        actor: str = "user",
        run_id: Optional[UUID] = None,
    ) -> Application:
        """Approve an application in AWAITING_APPROVAL with strict security checks.

        Rules:
        - Must verify ownership server-side.
        - Must not approve expired applications.
        - Rejects blocked, ineligible, or terminal applications.
        - Prevents approval reuse.
        - Emits immutable audit log with actor and timestamp.
        """
        app = await self.application_repo.get_by_id(application_id)
        if not app:
            raise ApplicationNotFoundError(f"Application '{application_id}' not found.")

        # Server-side ownership verification
        if app.user_id != user_id:
            logger.warning(
                "Security alert: User %s attempted to approve application %s owned by %s",
                user_id,
                application_id,
                app.user_id,
            )
            raise ApprovalAuthorizationError("Unauthorized: Application belongs to another user.")

        # State checks
        if app.status in (
            ApplicationStatus.APPLIED,
            ApplicationStatus.DRY_RUN_DONE,
            ApplicationStatus.SKIPPED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.EXPIRED,
            ApplicationStatus.DUPLICATE,
            ApplicationStatus.FAILED,
        ):
            raise TerminalStateError(app.status.value, ApplicationStatus.FILLING.value)

        if app.status == ApplicationStatus.BLOCKED:
            raise ApprovalStateError("Cannot approve application blocked by safety or policy.")

        if app.status != ApplicationStatus.AWAITING_APPROVAL:
            raise ApprovalStateError(
                f"Application is not awaiting approval (current status: {app.status.value})."
            )

        # Check for expiry
        now = datetime.now(timezone.utc)
        age = now - app.updated_at
        if age > timedelta(hours=self.default_ttl_hours):
            expired_app = await self._expire_application(
                app, reason=f"Approval expired: exceeded {self.default_ttl_hours}h limit"
            )
            raise ApprovalExpiredError(f"Approval window for application '{application_id}' has expired.")

        # Delegate transition to orchestrator
        approved_app = await self.orchestrator.approve(
            application_id=application_id,
            user_id=user_id,
            run_id=run_id,
        )

        # Record explicit audit event with actor
        audit_event = ApplicationEvent(
            application_id=application_id,
            event_type="APPROVAL_GRANTED",
            previous_status=ApplicationStatus.AWAITING_APPROVAL,
            new_status=ApplicationStatus.FILLING,
            reason=f"Approved by actor: {actor}",
            triggering_component="ApprovalManager",
            run_id=run_id,
            payload={
                "actor": actor,
                "user_id": str(user_id),
                "approved_at": now.isoformat(),
            },
            timestamp=now,
        )
        await self.event_repo.append_event(audit_event)
        return approved_app

    async def reject_application(
        self,
        application_id: UUID,
        user_id: UUID,
        reason: str = "Rejected by user",
        actor: str = "user",
        run_id: Optional[UUID] = None,
    ) -> Application:
        """Reject an application explicitly, recording actor and reason."""
        app = await self.application_repo.get_by_id(application_id)
        if not app:
            raise ApplicationNotFoundError(f"Application '{application_id}' not found.")

        if app.user_id != user_id:
            raise ApprovalAuthorizationError("Unauthorized: Application belongs to another user.")

        rejected_app = await self.orchestrator.reject(
            application_id=application_id,
            user_id=user_id,
            reason=reason,
            run_id=run_id,
        )

        now = datetime.now(timezone.utc)
        audit_event = ApplicationEvent(
            application_id=application_id,
            event_type="APPROVAL_REJECTED",
            previous_status=app.status,
            new_status=ApplicationStatus.REJECTED,
            reason=f"Rejected by actor: {actor}. Reason: {reason}",
            triggering_component="ApprovalManager",
            run_id=run_id,
            payload={
                "actor": actor,
                "user_id": str(user_id),
                "reason": reason,
                "rejected_at": now.isoformat(),
            },
            timestamp=now,
        )
        await self.event_repo.append_event(audit_event)
        return rejected_app

    async def resolve_user_input(
        self,
        application_id: UUID,
        user_id: UUID,
        provided_answers: Dict[str, Any],
        actor: str = "user",
        run_id: Optional[UUID] = None,
    ) -> Application:
        """Provide candidate answers for an application in NEEDS_USER_INPUT.

        Transitions: NEEDS_USER_INPUT -> READY -> AWAITING_APPROVAL
        """
        app = await self.application_repo.get_by_id(application_id)
        if not app:
            raise ApplicationNotFoundError(f"Application '{application_id}' not found.")

        if app.user_id != user_id:
            raise ApprovalAuthorizationError("Unauthorized: Application belongs to another user.")

        if app.status != ApplicationStatus.NEEDS_USER_INPUT:
            raise ApprovalStateError(
                f"Application is not in NEEDS_USER_INPUT status (current: {app.status.value})."
            )

        now = datetime.now(timezone.utc)

        # Transition NEEDS_USER_INPUT -> FILLING (per Section 13 state machine)
        filling_app, event_filling = self.orchestrator.state_machine.transition(
            application=app,
            target_status=ApplicationStatus.FILLING,
            reason=f"Missing answers provided by {actor} ({len(provided_answers)} fields)",
            triggering_component="ApprovalManager",
            run_id=run_id,
            payload={"answers_count": len(provided_answers)},
        )
        await self.application_repo.update(filling_app)
        await self.event_repo.append_event(event_filling)
        return filling_app

    async def handle_stale_approvals(self, max_age_hours: Optional[float] = None) -> List[Application]:
        """Scan and transition pending approvals older than TTL to EXPIRED."""
        ttl = max_age_hours or self.default_ttl_hours
        now = datetime.now(timezone.utc)
        expired_apps: List[Application] = []

        # Find all pending approvals across applications
        pending_apps = await self.application_repo.list_by_status(status=ApplicationStatus.AWAITING_APPROVAL)
        for app in pending_apps:
            age = now - app.updated_at
            if age > timedelta(hours=ttl):
                expired = await self._expire_application(
                    app, reason=f"Stale approval expired after {ttl}h inactivity"
                )
                expired_apps.append(expired)

        return expired_apps

    async def get_safe_application_detail(
        self, application_id: UUID, user_id: UUID
    ) -> Dict[str, Any]:
        """Return safe, sanitized application details for UI/Telegram without exposing secrets or raw PII."""
        app = await self.application_repo.get_by_id(application_id)
        if not app:
            raise ApplicationNotFoundError(f"Application '{application_id}' not found.")

        if app.user_id != user_id:
            raise ApprovalAuthorizationError("Unauthorized: Application belongs to another user.")

        events = await self.event_repo.list_by_application_id(application_id)

        return {
            "id": str(app.id),
            "job_id": str(app.job_id),
            "platform": app.platform,
            "external_id": app.external_id,
            "status": app.status.value,
            "approval_status": app.approval_status.value if app.approval_status else None,
            "autonomy_level": app.autonomy_level.value,
            "score": app.score,
            "evidence_ref": app.evidence_ref,
            "created_at": app.created_at.isoformat(),
            "updated_at": app.updated_at.isoformat(),
            "approved_at": app.approved_at.isoformat() if app.approved_at else None,
            "events_count": len(events),
            "recent_events": [
                {
                    "event_type": e.event_type,
                    "previous_status": e.previous_status.value if e.previous_status else None,
                    "new_status": e.new_status.value if e.new_status else None,
                    "reason": e.reason,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in events[-5:]
            ],
        }

    async def _expire_application(self, app: Application, reason: str) -> Application:
        """Internal helper to transition an application to EXPIRED."""
        expired_app, event = self.orchestrator.state_machine.transition(
            application=app,
            target_status=ApplicationStatus.EXPIRED,
            reason=reason,
            triggering_component="ApprovalManager",
        )
        expired_app = expired_app.model_copy(
            update={"approval_status": ApprovalStatus.EXPIRED}
        )
        await self.application_repo.update(expired_app)
        await self.event_repo.append_event(event)
        return expired_app
