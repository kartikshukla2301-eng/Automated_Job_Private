"""Central Job Provider Registry managing discovery and form execution adapters.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 11, 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Set
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from worker.providers.base import JobDiscoveryAdapter, JobProvider

logger = logging.getLogger("worker.providers.registry")


class ProviderMetadata(BaseModel):
    """Metadata describing a supported job platform provider."""

    name: str = Field(..., description="Normalized provider key (e.g. 'greenhouse')")
    display_name: str = Field(..., description="Human-readable provider label")
    auth_required: bool = Field(default=False, description="Whether manual candidate login session is required")
    supported_domains: List[str] = Field(default_factory=list, description="Hostnames associated with this provider")
    has_discovery: bool = Field(default=True, description="Whether job discovery adapter is available")
    has_form_inspection: bool = Field(default=True, description="Whether form inspection/dry-run is available")


class ProviderRegistrationError(Exception):
    """Raised when provider registration or lookup fails."""
    pass


class ProviderRegistry:
    """Thread-safe registry for job board and ATS providers."""

    def __init__(self) -> None:
        self._metadata: Dict[str, ProviderMetadata] = {}
        self._providers: Dict[str, JobProvider] = {}
        self._discovery_adapters: Dict[str, JobDiscoveryAdapter] = {}

    def register(
        self,
        metadata: ProviderMetadata,
        provider: Optional[JobProvider] = None,
        discovery_adapter: Optional[JobDiscoveryAdapter] = None,
    ) -> None:
        """Register a provider with its metadata, runner provider, and discovery adapter."""
        name = metadata.name.lower().strip()
        self._metadata[name] = metadata
        if provider is not None:
            self._providers[name] = provider
        if discovery_adapter is not None:
            self._discovery_adapters[name] = discovery_adapter
        logger.info("Registered provider in registry: %s", name)

    def get_provider(self, name: str) -> JobProvider:
        """Retrieve execution provider by normalized name."""
        key = name.lower().strip()
        if key not in self._providers:
            raise ProviderRegistrationError(f"No execution provider registered for: '{name}'")
        return self._providers[key]

    def get_discovery_adapter(self, name: str) -> JobDiscoveryAdapter:
        """Retrieve discovery adapter by normalized name."""
        key = name.lower().strip()
        if key not in self._discovery_adapters:
            raise ProviderRegistrationError(f"No discovery adapter registered for: '{name}'")
        return self._discovery_adapters[key]

    def get_metadata(self, name: str) -> Optional[ProviderMetadata]:
        """Get provider metadata by normalized name."""
        return self._metadata.get(name.lower().strip())

    def list_providers(self) -> List[str]:
        """Return list of all registered provider names."""
        return sorted(list(self._metadata.keys()))

    def is_registered(self, name: str) -> bool:
        """Check if provider is registered."""
        return name.lower().strip() in self._metadata

    def detect_provider_from_url(self, url: str) -> Optional[str]:
        """Detect registered provider name from a job URL."""
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            for name, meta in self._metadata.items():
                for domain in meta.supported_domains:
                    if host == domain or host.endswith("." + domain):
                        return name
            return None
        except Exception as err:
            logger.warning("Error detecting provider from url '%s': %s", url, err)
            return None


def create_default_registry() -> ProviderRegistry:
    """Build and return pre-configured registry containing all standard providers."""
    from worker.providers.greenhouse import GreenhouseProvider
    from worker.providers.greenhouse_discovery import GreenhouseDiscoveryAdapter
    from worker.providers.lever import LeverProvider
    from worker.providers.lever_discovery import LeverDiscoveryAdapter
    from worker.providers.naukri import NaukriDiscoveryAdapter, NaukriProvider
    from worker.providers.wellfound import WellfoundDiscoveryAdapter, WellfoundProvider
    from worker.providers.ashby import AshbyDiscoveryAdapter, AshbyProvider

    registry = ProviderRegistry()

    # Greenhouse
    registry.register(
        metadata=ProviderMetadata(
            name="greenhouse",
            display_name="Greenhouse",
            auth_required=False,
            supported_domains=["boards.greenhouse.io", "job-boards.greenhouse.io"],
            has_discovery=True,
            has_form_inspection=True,
        ),
        provider=GreenhouseProvider(),
        discovery_adapter=GreenhouseDiscoveryAdapter(),
    )

    # Lever
    registry.register(
        metadata=ProviderMetadata(
            name="lever",
            display_name="Lever",
            auth_required=False,
            supported_domains=["jobs.lever.co"],
            has_discovery=True,
            has_form_inspection=True,
        ),
        provider=LeverProvider(),
        discovery_adapter=LeverDiscoveryAdapter(),
    )

    # Naukri
    registry.register(
        metadata=ProviderMetadata(
            name="naukri",
            display_name="Naukri",
            auth_required=True,
            supported_domains=["naukri.com", "www.naukri.com"],
            has_discovery=True,
            has_form_inspection=True,
        ),
        provider=NaukriProvider(),
        discovery_adapter=NaukriDiscoveryAdapter(),
    )

    # Wellfound
    registry.register(
        metadata=ProviderMetadata(
            name="wellfound",
            display_name="Wellfound",
            auth_required=True,
            supported_domains=["wellfound.com", "www.wellfound.com", "angel.co"],
            has_discovery=True,
            has_form_inspection=True,
        ),
        provider=WellfoundProvider(),
        discovery_adapter=WellfoundDiscoveryAdapter(),
    )

    # Ashby
    registry.register(
        metadata=ProviderMetadata(
            name="ashby",
            display_name="Ashby",
            auth_required=False,
            supported_domains=["ashbyhq.com", "jobs.ashbyhq.com"],
            has_discovery=True,
            has_form_inspection=True,
        ),
        provider=AshbyProvider(),
        discovery_adapter=AshbyDiscoveryAdapter(),
    )

    return registry
