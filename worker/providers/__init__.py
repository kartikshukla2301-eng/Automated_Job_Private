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
from worker.providers.wellfound import (
    WellfoundDiscoveryAdapter,
    WellfoundProvider,
    WellfoundSessionManager,
    WellfoundSessionStatus,
)
from worker.providers.ashby import (
    AshbyDiscoveryAdapter,
    AshbyProvider,
)
from worker.providers.linkedin import (
    LinkedInDiscoveryAdapter,
    LinkedInLoginWallError,
    LinkedInProvider,
    LinkedInSecurityCheckpointError,
    LinkedInSessionManager,
    LinkedInSessionStatus,
)
from worker.providers.registry import (
    ProviderMetadata,
    ProviderRegistrationError,
    ProviderRegistry,
    create_default_registry,
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
    "WellfoundDiscoveryAdapter",
    "WellfoundProvider",
    "WellfoundSessionManager",
    "WellfoundSessionStatus",
    "AshbyDiscoveryAdapter",
    "AshbyProvider",
    "LinkedInDiscoveryAdapter",
    "LinkedInLoginWallError",
    "LinkedInProvider",
    "LinkedInSecurityCheckpointError",
    "LinkedInSessionManager",
    "LinkedInSessionStatus",
    "ProviderMetadata",
    "ProviderRegistrationError",
    "ProviderRegistry",
    "create_default_registry",
    "ProviderDataError",
    "ProviderError",
    "ProviderNetworkError",
    "ProviderNotFoundError",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "UnsupportedProviderError",
    "UnsafeUrlError",
]
