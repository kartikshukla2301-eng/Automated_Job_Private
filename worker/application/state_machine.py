"""Explicit, code-enforced application lifecycle state machine.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 13)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Set, Tuple
from uuid import UUID

from worker.application.exceptions import (
    InvalidStateTransitionError,
    TerminalStateError,
)
from worker.application.models import (
    Application,
    ApplicationEvent,
    ApplicationEventType,
    ApplicationStatus,
)

# Canonical state transitions locked in Architecture v1.0 Section 13:
VALID_TRANSITIONS: Dict[ApplicationStatus, Set[ApplicationStatus]] = {
    ApplicationStatus.DISCOVERED: {
        ApplicationStatus.MATCHED,
        ApplicationStatus.DUPLICATE,
        ApplicationStatus.EXPIRED,
        ApplicationStatus.SKIPPED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.MATCHED: {
        ApplicationStatus.ELIGIBLE,
        ApplicationStatus.BLOCKED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.EXPIRED,
        ApplicationStatus.DUPLICATE,
        ApplicationStatus.SKIPPED,
    },
    ApplicationStatus.ELIGIBLE: {
        ApplicationStatus.READY,
        ApplicationStatus.BLOCKED,
        ApplicationStatus.SKIPPED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.EXPIRED,
    },
    ApplicationStatus.READY: {
        ApplicationStatus.AWAITING_APPROVAL,
        ApplicationStatus.FILLING,
        ApplicationStatus.SKIPPED,
        ApplicationStatus.EXPIRED,
    },
    ApplicationStatus.AWAITING_APPROVAL: {
        ApplicationStatus.FILLING,
        ApplicationStatus.REJECTED,
        ApplicationStatus.EXPIRED,
        ApplicationStatus.SKIPPED,
    },
    ApplicationStatus.FILLING: {
        ApplicationStatus.SUBMITTING,     # L2/L3 real submit only
        ApplicationStatus.DRY_RUN_DONE,   # L0 dry-run completion
        ApplicationStatus.NEEDS_USER_INPUT,
        ApplicationStatus.BLOCKED,
        ApplicationStatus.FAILED,
    },
    ApplicationStatus.NEEDS_USER_INPUT: {
        ApplicationStatus.FILLING,
        ApplicationStatus.SKIPPED,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.BLOCKED: {
        ApplicationStatus.FILLING,
        ApplicationStatus.EXPIRED,
        ApplicationStatus.FAILED,
        ApplicationStatus.SKIPPED,
    },
    ApplicationStatus.SUBMITTING: {
        ApplicationStatus.APPLIED,
        ApplicationStatus.UNCERTAIN,
        ApplicationStatus.FAILED,
    },
    ApplicationStatus.UNCERTAIN: {
        ApplicationStatus.VERIFYING,
        ApplicationStatus.FAILED,
    },
    ApplicationStatus.VERIFYING: {
        ApplicationStatus.APPLIED,
        ApplicationStatus.READY,          # RC-3: only if verified NOT applied
        ApplicationStatus.FAILED,
    },
    # Terminal outcomes: Section 13 allows manual retry for FAILED
    ApplicationStatus.FAILED: {
        ApplicationStatus.READY,
    },
    ApplicationStatus.APPLIED: set(),
    ApplicationStatus.DRY_RUN_DONE: set(),
    ApplicationStatus.SKIPPED: set(),
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.EXPIRED: set(),
    ApplicationStatus.DUPLICATE: set(),
}

TERMINAL_STATUSES: Set[ApplicationStatus] = {
    ApplicationStatus.APPLIED,
    ApplicationStatus.DRY_RUN_DONE,
    ApplicationStatus.SKIPPED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.EXPIRED,
    ApplicationStatus.DUPLICATE,
    ApplicationStatus.FAILED,
}


def is_terminal_status(status: ApplicationStatus) -> bool:
    """Return True if status is terminal."""
    return status in TERMINAL_STATUSES


class ApplicationStateMachine:
    """Deterministic, code-enforced state machine governing application status transitions."""

    def __init__(self, clock: Optional[Callable[[], datetime]] = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def validate_transition(
        self,
        current_status: ApplicationStatus,
        target_status: ApplicationStatus,
    ) -> None:
        """Validate whether a transition is permitted by Section 13 rules.

        Raises:
            TerminalStateError: If current_status is terminal (except FAILED -> READY manual retry).
            InvalidStateTransitionError: If target_status is not in valid next states.
        """
        if current_status == target_status:
            return

        if is_terminal_status(current_status):
            # Section 13 explicitly specifies: "Manual retry allowed for FAILED -> READY"
            if current_status == ApplicationStatus.FAILED and target_status == ApplicationStatus.READY:
                return
            raise TerminalStateError(current_status.value, target_status.value)

        allowed = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise InvalidStateTransitionError(
                current_status=current_status.value,
                attempted_status=target_status.value,
                reason=f"Allowed transitions from '{current_status.value}': {[s.value for s in allowed]}",
            )

    def transition(
        self,
        application: Application,
        target_status: ApplicationStatus,
        reason: Optional[str] = None,
        triggering_component: Optional[str] = None,
        run_id: Optional[UUID] = None,
        payload: Optional[Dict[str, Any]] = None,
        evidence_ref: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Tuple[Application, ApplicationEvent]:
        """Perform a validated transition and return (updated_application, audit_event).

        Guarantees that state update and event creation are consistent.
        """
        self.validate_transition(application.status, target_status)
        now = self._clock()

        update_fields: Dict[str, Any] = {
            "status": target_status,
            "updated_at": now,
        }

        if run_id is not None:
            update_fields["run_id"] = run_id
        if evidence_ref is not None:
            update_fields["evidence_ref"] = evidence_ref
        if error is not None:
            update_fields["error"] = error
        if target_status == ApplicationStatus.APPLIED:
            update_fields["applied_at"] = now

        updated_app = application.model_copy(update=update_fields)

        event = ApplicationEvent(
            application_id=application.id,
            event_type=ApplicationEventType.STATE_TRANSITION.value,
            previous_status=application.status,
            new_status=target_status,
            reason=reason,
            triggering_component=triggering_component or "ApplicationStateMachine",
            run_id=run_id or application.run_id,
            payload=payload or {},
            timestamp=now,
        )

        return updated_app, event
