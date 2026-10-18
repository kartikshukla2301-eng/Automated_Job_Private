"""Typed safety and execution barrier exceptions."""


class SafetyBlockedError(Exception):
    """Base exception raised when an action is blocked by the safety engine."""


class KillSwitchActiveError(SafetyBlockedError):
    """Raised when automation is blocked because the kill switch is active or engaged."""


class InvalidSafetyStateError(SafetyBlockedError):
    """Raised when safety state is missing, corrupt, or inaccessible, triggering fail-closed."""


class CapExceededError(SafetyBlockedError):
    """Base exception for application cap limit violations."""


class GlobalDailyCapExceededError(CapExceededError):
    """Raised when total daily applications exceed the global ceiling."""


class ProviderDailyCapExceededError(CapExceededError):
    """Raised when applications for a specific job board exceed its daily ceiling."""


class CompanyDailyCapExceededError(CapExceededError):
    """Raised when applications to a single company exceed the 24-hour ceiling."""


class CompanyCooldownExceededError(CapExceededError):
    """Raised when applications to a single company exceed the 30-day cooldown ceiling."""


class RealSubmitGateBlockedError(SafetyBlockedError):
    """Raised when a real submission is attempted while real submissions are locked."""
