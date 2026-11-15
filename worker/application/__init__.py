"""Application lifecycle state machine and orchestration package exports.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 13, 14)
"""

from worker.application.exceptions import (
    ApplicationError,
    ApplicationNotFoundError,
    ApprovalRequiredError,
    DuplicateApplicationError,
    IdempotencyConflictError,
    InvalidStateTransitionError,
    RecoveryError,
    SafetyGateError,
    TerminalStateError,
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
from worker.application.orchestrator import ApplicationOrchestrator
from worker.application.repository import (
    ApplicationEventRepository,
    ApplicationRepository,
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)
from worker.application.state_machine import (
    TERMINAL_STATUSES,
    VALID_TRANSITIONS,
    ApplicationStateMachine,
    is_terminal_status,
)

__all__ = [
    "Application",
    "ApplicationError",
    "ApplicationEvent",
    "ApplicationEventRepository",
    "ApplicationEventType",
    "ApplicationNotFoundError",
    "ApplicationOrchestrator",
    "ApplicationRepository",
    "ApplicationStateMachine",
    "ApplicationStatus",
    "ApprovalRequiredError",
    "ApprovalStatus",
    "AutonomyLevel",
    "DuplicateApplicationError",
    "IdempotencyConflictError",
    "InMemoryApplicationEventRepository",
    "InMemoryApplicationRepository",
    "InvalidStateTransitionError",
    "RecoveryError",
    "SafetyGateError",
    "TERMINAL_STATUSES",
    "TerminalStateError",
    "VALID_TRANSITIONS",
    "generate_application_idempotency_key",
    "is_terminal_status",
]
