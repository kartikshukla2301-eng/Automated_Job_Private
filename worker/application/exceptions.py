"""Domain exceptions for application lifecycle and state machine.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 13)
- docs/BUILD_RULES.md
"""


class ApplicationError(Exception):
    """Base exception for all application lifecycle errors."""


class InvalidStateTransitionError(ApplicationError):
    """Raised when an illegal status transition is attempted."""

    def __init__(self, current_status: str, attempted_status: str, reason: str = "") -> None:
        self.current_status = current_status
        self.attempted_status = attempted_status
        msg = f"Invalid state transition from '{current_status}' to '{attempted_status}'."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg)


class TerminalStateError(ApplicationError):
    """Raised when attempting to transition out of an immutable terminal state."""

    def __init__(self, terminal_status: str, attempted_status: str) -> None:
        self.terminal_status = terminal_status
        self.attempted_status = attempted_status
        super().__init__(
            f"Cannot transition out of terminal state '{terminal_status}' to '{attempted_status}'."
        )


class DuplicateApplicationError(ApplicationError):
    """Raised when attempting to create an application that already exists for a (user_id, job_id) pair."""

    def __init__(self, user_id: str, job_id: str) -> None:
        self.user_id = user_id
        self.job_id = job_id
        super().__init__(f"Application already exists for user '{user_id}' and job '{job_id}'.")


class IdempotencyConflictError(ApplicationError):
    """Raised when an idempotency key matches an existing application with conflicting parameters."""

    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(f"Idempotency conflict for key '{idempotency_key}'.")


class ApplicationNotFoundError(ApplicationError):
    """Raised when an application is not found by ID or query criteria."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"Application '{identifier}' not found.")


class ApprovalRequiredError(ApplicationError):
    """Raised when an operation requires explicit user approval before execution."""

    def __init__(self, application_id: str, status: str) -> None:
        self.application_id = application_id
        self.status = status
        super().__init__(
            f"Application '{application_id}' is in status '{status}' and requires explicit user approval."
        )


class SafetyGateError(ApplicationError):
    """Raised when safety barrier (kill switch, caps, cooldown) blocks application progress."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Safety gate blocked application: {reason}")


class RecoveryError(ApplicationError):
    """Raised when recovering an interrupted application fails safety validation."""
