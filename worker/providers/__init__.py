"""Job provider adapters: Greenhouse, Lever, and base contracts."""

from worker.providers.base import FormField, FormFillResult, JobDiscoveryAdapter, JobProvider
from worker.providers.exceptions import (
    ProviderDataError,
    ProviderError,
    ProviderNetworkError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    UnsupportedProviderError,
    UnsafeUrlError,
)
from worker.providers.greenhouse import GreenhouseProvider
from worker.providers.greenhouse_discovery import GreenhouseDiscoveryAdapter
from worker.providers.lever_discovery import LeverDiscoveryAdapter
from worker.providers.naukri import (
    NaukriDiscoveryAdapter,
    NaukriProvider,
    NaukriSessionManager,
    NaukriSessionStatus,
)

__all__ = [
    "FormField",
    "FormFillResult",
    "GreenhouseDiscoveryAdapter",
    "GreenhouseProvider",
    "JobDiscoveryAdapter",
    "JobProvider",
    "LeverDiscoveryAdapter",
    "NaukriDiscoveryAdapter",
    "NaukriProvider",
    "NaukriSessionManager",
    "NaukriSessionStatus",
    "ProviderDataError",
    "ProviderError",
    "ProviderNetworkError",
    "ProviderNotFoundError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "UnsupportedProviderError",
    "UnsafeUrlError",
]
