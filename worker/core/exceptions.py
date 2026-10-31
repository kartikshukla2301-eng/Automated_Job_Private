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


# ==============================================================================
# LLM Gateway and Runtime AI Exceptions (Phase 0.9)
# ==============================================================================


class LLMGatewayError(Exception):
    """Base exception for all central LLM Gateway failures."""


class LLMAuthenticationError(LLMGatewayError):
    """Raised when OpenRouter API credentials are missing, empty, or rejected."""


class LLMBudgetExceededError(LLMGatewayError):
    """Raised when daily LLM call or cost quotas are exhausted."""


class LLMCircuitBreakerOpenError(LLMGatewayError):
    """Raised when the gateway circuit breaker is OPEN due to repeated provider failures."""


class LLMProviderError(LLMGatewayError):
    """Raised when the upstream provider returns an HTTP error, 5xx, or network failure."""


class LLMTimeoutError(LLMProviderError):
    """Raised when an LLM provider request exceeds its configured timeout."""


class LLMMalformedResponseError(LLMGatewayError):
    """Raised when provider returns an unparseable or schema-violating payload."""


class LLMDegradedModeError(LLMGatewayError):
    """Raised when operating in degraded mode and a requested task cannot be satisfied."""


# =====================================================================
# Answer Bank & Policy Engine Exceptions (Phase 1.0)
# =====================================================================


class AnswerBankError(Exception):
    """Base exception for all Answer Bank operations."""


class InvalidAnswerEntryError(AnswerBankError):
    """Raised when an Answer Bank record is malformed or invalid."""


class ExpiredAnswerError(AnswerBankError):
    """Raised when an Answer Bank record has passed its valid_until date."""


class AmbiguousAnswerError(AnswerBankError):
    """Raised when multiple conflicting answers match a single query."""


class PolicyViolationError(AnswerBankError):
    """Raised when an action violates code-enforced PolicyEngine rules."""
