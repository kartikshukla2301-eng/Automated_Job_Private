"""Domain exceptions for Playwright browser runtime and form execution foundation.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12, 13)
- docs/BUILD_RULES.md
"""


class BrowserRuntimeError(Exception):
    """Base exception for all browser runtime and automation errors."""


class NavigationError(BrowserRuntimeError):
    """Raised when page navigation fails or violates security constraints."""


class UnsupportedDestinationError(NavigationError):
    """Raised when navigation target is not in the approved provider origins list."""

    def __init__(self, target_url: str, reason: str = "") -> None:
        self.target_url = target_url
        self.reason = reason
        msg = f"Navigation blocked to unsupported destination '{target_url}'."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(msg)


class PrivateNetworkTargetError(UnsupportedDestinationError):
    """Raised when navigation targets localhost, loopback, link-local, or private RFC1918 addresses."""

    def __init__(self, target_url: str, hostname_or_ip: str) -> None:
        self.hostname_or_ip = hostname_or_ip
        super().__init__(
            target_url=target_url,
            reason=f"Target resolves to prohibited private or loopback address '{hostname_or_ip}'.",
        )


class SessionError(BrowserRuntimeError):
    """Base exception for browser session lifecycle issues."""


class SessionNotFoundError(SessionError):
    """Raised when requested browser session does not exist or has expired."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        super().__init__(f"Browser session '{session_id}' not found.")


class SessionTimeoutError(SessionError):
    """Raised when a browser session or operation exceeds its configured deadline."""

    def __init__(self, operation: str, timeout_ms: int) -> None:
        self.operation = operation
        self.timeout_ms = timeout_ms
        super().__init__(f"Operation '{operation}' timed out after {timeout_ms}ms.")


class SessionCancelledError(SessionError):
    """Raised when a browser session or operation is cancelled by user or safety interrupt."""

    def __init__(self, session_id: str, reason: str = "") -> None:
        self.session_id = session_id
        self.reason = reason
        super().__init__(f"Browser session '{session_id}' cancelled: {reason or 'User/Safety cancel'}")


class FormInspectionError(BrowserRuntimeError):
    """Raised when inspecting form elements or extracting DOM metadata fails."""


class EvidenceCaptureError(BrowserRuntimeError):
    """Raised when capturing DOM snapshot, screenshot, or audit metadata fails."""


class UnsafeActionError(BrowserRuntimeError):
    """Raised when an operation attempts to violate L0 safety rules (e.g. submit, candidate data entry)."""
