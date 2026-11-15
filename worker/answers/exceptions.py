"""Typed exceptions for Answer Bank and resolution operations."""


class AnswerBankError(Exception):
    """Base exception for all Answer Bank operations."""


class InvalidAnswerEntryError(AnswerBankError):
    """Raised when an Answer Bank record is malformed or invalid."""


class AnswerNotFoundError(AnswerBankError):
    """Raised when an expected Answer Bank record is not found."""


class ExpiredAnswerError(AnswerBankError):
    """Raised when an Answer Bank record has passed its valid_until date."""


class AmbiguousAnswerError(AnswerBankError):
    """Raised when multiple conflicting answers match a single query."""


class PolicyViolationError(AnswerBankError):
    """Raised when an action violates the code-enforced PolicyEngine rules."""
