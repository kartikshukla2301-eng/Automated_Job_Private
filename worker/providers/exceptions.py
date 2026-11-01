"""Typed provider adapter and discovery exceptions."""


class ProviderError(Exception):
    """Base exception for provider adapter operations."""


class ProviderNetworkError(ProviderError):
    """Raised when provider request fails due to network or connection issues."""


class ProviderTimeoutError(ProviderNetworkError):
    """Raised when provider request times out."""


class ProviderNotFoundError(ProviderError):
    """Raised when the target company or job board is not found (HTTP 404)."""


class ProviderRateLimitError(ProviderError):
    """Raised when the provider throttles requests (HTTP 429)."""


class ProviderDataError(ProviderError):
    """Raised when provider returns unparseable or malformed data."""


class UnsupportedProviderError(ProviderError):
    """Raised when a requested provider is not supported."""


class UnsafeUrlError(ProviderError):
    """Raised when an external URL violates network boundaries or allowed hosts."""
