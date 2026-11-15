"""Unit tests for Central Provider Registry (Phase 1.7).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 11, 12)
- docs/BUILD_RULES.md
"""

import pytest

from worker.providers.registry import (
    ProviderMetadata,
    ProviderRegistrationError,
    ProviderRegistry,
    create_default_registry,
)


def test_default_registry_initialization():
    registry = create_default_registry()

    providers = registry.list_providers()
    assert "greenhouse" in providers
    assert "lever" in providers
    assert "naukri" in providers
    assert "wellfound" in providers
    assert "ashby" in providers
    assert len(providers) >= 5

    # Check metadata
    gh_meta = registry.get_metadata("greenhouse")
    assert gh_meta is not None
    assert gh_meta.auth_required is False
    assert "boards.greenhouse.io" in gh_meta.supported_domains

    wf_meta = registry.get_metadata("wellfound")
    assert wf_meta is not None
    assert wf_meta.auth_required is True

    naukri_meta = registry.get_metadata("naukri")
    assert naukri_meta is not None
    assert naukri_meta.auth_required is True


def test_registry_get_provider_and_adapters():
    registry = create_default_registry()

    # Greenhouse
    gh_provider = registry.get_provider("greenhouse")
    gh_adapter = registry.get_discovery_adapter("greenhouse")
    assert gh_provider is not None
    assert gh_adapter is not None

    # Ashby
    ashby_provider = registry.get_provider("ashby")
    ashby_adapter = registry.get_discovery_adapter("ashby")
    assert ashby_provider is not None
    assert ashby_adapter is not None

    # Unregistered provider raises ProviderRegistrationError
    with pytest.raises(ProviderRegistrationError):
        registry.get_provider("unknown_provider")

    with pytest.raises(ProviderRegistrationError):
        registry.get_discovery_adapter("unknown_provider")


def test_registry_url_detection():
    registry = create_default_registry()

    assert registry.detect_provider_from_url("https://boards.greenhouse.io/acme/jobs/123") == "greenhouse"
    assert registry.detect_provider_from_url("https://jobs.lever.co/example/456") == "lever"
    assert registry.detect_provider_from_url("https://www.naukri.com/job-listings-123") == "naukri"
    assert registry.detect_provider_from_url("https://wellfound.com/jobs/8901") == "wellfound"
    assert registry.detect_provider_from_url("https://jobs.ashbyhq.com/cloudscale/401") == "ashby"
    assert registry.detect_provider_from_url("https://unknown-board.com/job/1") is None


def test_custom_registration():
    reg = ProviderRegistry()
    assert len(reg.list_providers()) == 0

    meta = ProviderMetadata(
        name="custom_ats",
        display_name="Custom ATS",
        auth_required=False,
        supported_domains=["customats.io"],
    )
    reg.register(meta)

    assert reg.is_registered("custom_ats") is True
    assert reg.detect_provider_from_url("https://customats.io/jobs/1") == "custom_ats"
