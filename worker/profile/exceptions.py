"""Typed exceptions for candidate profile operations."""


class ProfileError(Exception):
    """Base exception for all profile-related errors."""


class ProfileNotFoundError(ProfileError):
    """Raised when the specified profile file or resource cannot be found."""


class ProfileParseError(ProfileError):
    """Raised when profile content cannot be parsed (e.g. malformed YAML/JSON)."""


class ProfileValidationError(ProfileError):
    """Raised when profile content fails structural or typed model validation."""


class DevLevelerAuthError(ProfileError):
    """Raised when DevLeveler API authentication fails (401/403)."""


class DevLevelerConnectionError(ProfileError):
    """Raised when DevLeveler API network connection or server error occurs."""


class HallucinationDetectedError(ProfileError):
    """Raised when tailored resume or cover letter contains unverified assertions not grounded in candidate profile."""
