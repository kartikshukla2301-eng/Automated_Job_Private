"""Tests for NavigationGuard origin enforcement and anti-SSRF protections.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12)
- docs/BUILD_RULES.md
"""

from pathlib import Path
import pytest

from worker.browser.exceptions import (
    NavigationError,
    PrivateNetworkTargetError,
    UnsupportedDestinationError,
)
from worker.browser.navigation_guard import NavigationGuard


@pytest.fixture
def guard() -> NavigationGuard:
    return NavigationGuard(fixtures_dir=Path("fixtures"))


def test_guard_allows_greenhouse_urls(guard: NavigationGuard):
    """Verify approved Greenhouse origins are permitted."""
    valid_url = "https://boards.greenhouse.io/examplesoftware/jobs/123456"
    assert guard.validate_url(valid_url) == valid_url

    valid_board_url = "https://job-boards.greenhouse.io/acme/jobs/7890"
    assert guard.validate_url(valid_board_url) == valid_board_url


def test_guard_allows_lever_urls(guard: NavigationGuard):
    """Verify approved Lever origins are permitted."""
    valid_url = "https://jobs.lever.co/acme/4a5b6c7d-8e9f-0123-4567-89abcdef0123"
    assert guard.validate_url(valid_url) == valid_url


def test_guard_rejects_unsupported_domains(guard: NavigationGuard):
    """Verify arbitrary external domains are blocked."""
    unsupported = [
        "https://example.com/apply",
        "https://workday.com/jobs/1",
        "https://malicious-site.io/hack",
        "https://greenhouse.fake-domain.com/jobs",
    ]
    for url in unsupported:
        with pytest.raises(UnsupportedDestinationError):
            guard.validate_url(url)


def test_guard_rejects_disallowed_schemes(guard: NavigationGuard):
    """Verify insecure HTTP, javascript:, data:, and FTP schemes are rejected."""
    insecure = [
        "http://boards.greenhouse.io/jobs/1",
        "javascript:alert(1)",
        "data:text/html,<html></html>",
        "ftp://boards.greenhouse.io/file",
        "ws://boards.greenhouse.io/socket",
    ]
    for target in insecure:
        with pytest.raises(UnsupportedDestinationError):
            guard.validate_url(target)


def test_guard_rejects_localhost_and_private_networks(guard: NavigationGuard):
    """Verify anti-SSRF blocks loopback, private RFC1918, and link-local ranges."""
    ssrf_targets = [
        "https://localhost/admin",
        "https://127.0.0.1:8000/keys",
        "https://10.0.0.1/metadata",
        "https://172.16.0.5/api",
        "https://192.168.1.1/router",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/secret",
    ]
    for target in ssrf_targets:
        with pytest.raises(PrivateNetworkTargetError):
            guard.validate_url(target)


def test_guard_allows_verified_local_fixture_file(guard: NavigationGuard):
    """Verify local HTML fixture file within approved fixtures directory is resolved."""
    fixture_path = Path("fixtures/forms/greenhouse_job.html")
    resolved_uri = guard.validate_url(str(fixture_path))
    assert resolved_uri.startswith("file://")
    assert "greenhouse_job.html" in resolved_uri


def test_guard_rejects_path_traversal_in_local_fixture(guard: NavigationGuard):
    """Verify path traversal outside fixtures/ directory is blocked."""
    traversal_targets = [
        "fixtures/forms/../../README.md",
        "fixtures/forms/../../config/config.yaml",
        "../outside_fixture.html",
    ]
    for target in traversal_targets:
        with pytest.raises(UnsupportedDestinationError):
            guard.validate_url(target)


def test_guard_rejects_nonexistent_local_fixture(guard: NavigationGuard):
    """Verify non-existent fixture path raises NavigationError."""
    with pytest.raises(NavigationError):
        guard.validate_url("fixtures/forms/non_existent_job.html")


def test_guard_validate_redirect(guard: NavigationGuard):
    """Verify redirect destinations are revalidated."""
    current = "https://boards.greenhouse.io/jobs/1"
    valid_redirect = "https://boards.greenhouse.io/jobs/2"
    invalid_redirect = "https://attacker.com/steal"

    # Valid redirect succeeds silently
    guard.validate_redirect(current, valid_redirect)

    # Invalid redirect raises UnsupportedDestinationError
    with pytest.raises(UnsupportedDestinationError):
        guard.validate_redirect(current, invalid_redirect)
