"""Unit tests for Application state machine and transition rules.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 13)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from worker.application.exceptions import (
    InvalidStateTransitionError,
    TerminalStateError,
)
from worker.application.models import (
    Application,
    ApplicationStatus,
    AutonomyLevel,
)
from worker.application.state_machine import (
    TERMINAL_STATUSES,
    VALID_TRANSITIONS,
    ApplicationStateMachine,
    is_terminal_status,
)


@pytest.fixture
def base_application() -> Application:
    now = datetime.now(timezone.utc)
    return Application(
        id=uuid4(),
        user_id=uuid4(),
        job_id=uuid4(),
        platform="greenhouse",
        external_id="gh-test-1",
        profile_version="v1.0.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.DISCOVERED,
        idempotency_key="idmp_test_base_1",
        created_at=now,
        updated_at=now,
    )


def test_state_machine_valid_discovered_transitions(base_application):
    sm = ApplicationStateMachine()
    for valid_next in [
        ApplicationStatus.MATCHED,
        ApplicationStatus.DUPLICATE,
        ApplicationStatus.EXPIRED,
        ApplicationStatus.SKIPPED,
        ApplicationStatus.REJECTED,
    ]:
        updated_app, event = sm.transition(base_application, valid_next, reason=f"Testing transition to {valid_next.value}")
        assert updated_app.status == valid_next
        assert event.previous_status == ApplicationStatus.DISCOVERED
        assert event.new_status == valid_next


def test_state_machine_rejects_invalid_transition(base_application):
    sm = ApplicationStateMachine()
    # DISCOVERED cannot jump directly to SUBMITTING or APPLIED or DRY_RUN_DONE
    with pytest.raises(InvalidStateTransitionError, match="Invalid state transition from 'DISCOVERED' to 'SUBMITTING'"):
        sm.transition(base_application, ApplicationStatus.SUBMITTING)

    with pytest.raises(InvalidStateTransitionError, match="Invalid state transition from 'DISCOVERED' to 'APPLIED'"):
        sm.transition(base_application, ApplicationStatus.APPLIED)

    with pytest.raises(InvalidStateTransitionError, match="Invalid state transition from 'DISCOVERED' to 'DRY_RUN_DONE'"):
        sm.transition(base_application, ApplicationStatus.DRY_RUN_DONE)


def test_state_machine_terminal_states_protection(base_application):
    sm = ApplicationStateMachine()

    # Immutable terminal states: APPLIED, DRY_RUN_DONE, SKIPPED, REJECTED, EXPIRED, DUPLICATE
    immutable_terminals = [
        ApplicationStatus.APPLIED,
        ApplicationStatus.DRY_RUN_DONE,
        ApplicationStatus.SKIPPED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.EXPIRED,
        ApplicationStatus.DUPLICATE,
    ]

    for terminal in immutable_terminals:
        assert is_terminal_status(terminal) is True
        term_app = base_application.model_copy(update={"status": terminal})
        with pytest.raises(TerminalStateError, match=f"Cannot transition out of terminal state '{terminal.value}'"):
            sm.transition(term_app, ApplicationStatus.READY)


def test_state_machine_failed_manual_retry_allowed(base_application):
    """Section 13 explicitly specifies: 'Manual retry allowed for FAILED' -> READY."""
    sm = ApplicationStateMachine()
    failed_app = base_application.model_copy(update={"status": ApplicationStatus.FAILED})

    # Allowed: FAILED -> READY
    ready_app, event = sm.transition(failed_app, ApplicationStatus.READY, reason="Manual user retry requested")
    assert ready_app.status == ApplicationStatus.READY
    assert event.previous_status == ApplicationStatus.FAILED
    assert event.new_status == ApplicationStatus.READY

    # Rejected: FAILED -> FILLING (must go to READY first)
    with pytest.raises(TerminalStateError):
        sm.transition(failed_app, ApplicationStatus.FILLING)


def test_state_machine_deterministic_clock_injection(base_application):
    fixed_time = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
    sm = ApplicationStateMachine(clock=lambda: fixed_time)

    updated_app, event = sm.transition(base_application, ApplicationStatus.MATCHED, reason="Clock test")
    assert updated_app.updated_at == fixed_time
    assert event.timestamp == fixed_time


def test_state_machine_every_transition_creates_audit_event(base_application):
    sm = ApplicationStateMachine()
    run_id = uuid4()
    updated_app, event = sm.transition(
        base_application,
        ApplicationStatus.MATCHED,
        reason="Passing threshold",
        triggering_component="TestComponent",
        run_id=run_id,
        payload={"score": 85.5},
    )

    assert event.application_id == base_application.id
    assert event.event_type == "STATE_TRANSITION"
    assert event.previous_status == ApplicationStatus.DISCOVERED
    assert event.new_status == ApplicationStatus.MATCHED
    assert event.reason == "Passing threshold"
    assert event.triggering_component == "TestComponent"
    assert event.run_id == run_id
    assert event.payload == {"score": 85.5}
