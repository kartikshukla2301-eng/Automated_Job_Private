"""Tests for Naukri Provider Adapter, Discovery, and Session Management (Phase 1.6).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 11, 12)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
import pytest

from worker.browser.exceptions import UnsupportedDestinationError
from worker.browser.navigation_guard import NavigationGuard
from worker.browser.page_inspector import PageInspector
from worker.core.exceptions import RealSubmitGateBlockedError
from worker.discovery.models import JobStatus
from worker.matching.deduplication import (
    DuplicateClassification,
    classify_duplicate_relationship,
)
from worker.profile.models import (
    CandidateDetails,
    CandidatePreferences,
    ProfileSnapshot,
)
from worker.providers.naukri import (
    NaukriDiscoveryAdapter,
    NaukriProvider,
    NaukriSessionManager,
    NaukriSessionStatus,
)


@pytest.fixture
def mock_profile():
    return ProfileSnapshot(
        schema_version=1,
        profile_version="v1.0-test",
        candidate=CandidateDetails(
            name="Jane Doe",
            email="jane.doe@example.com",
            phone="+919876543210",
            location="Bangalore, India",
        ),
        preferences=CandidatePreferences(
            roles=["Senior Python Developer"],
            locations=["Bangalore"],
            work_modes=["remote", "hybrid"],
        ),
    )


def test_naukri_session_manager_statuses(tmp_path):
    sess_file = tmp_path / "naukri_sess.json"
    mgr = NaukriSessionManager(session_path=sess_file)

    # Empty session -> LOGIN_REQUIRED
    assert mgr.inspect_session_status() == NaukriSessionStatus.LOGIN_REQUIRED

    # Active session -> LOGGED_IN
    future_time = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    mgr.save_session({"auth_token": "token-123", "expires_at": future_time})
    assert mgr.inspect_session_status() == NaukriSessionStatus.LOGGED_IN

    # Expired session -> SESSION_EXPIRED
    past_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    mgr.save_session({"auth_token": "token-123", "expires_at": past_time})
    assert mgr.inspect_session_status() == NaukriSessionStatus.SESSION_EXPIRED


def test_naukri_session_manager_never_stores_passwords(tmp_path):
    sess_file = tmp_path / "naukri_sess.json"
    mgr = NaukriSessionManager(session_path=sess_file)

    mgr.save_session({"auth_token": "secret-tok", "user_password": "PlainPassword123!"})
    data = mgr.load_session()
    assert "user_password" not in data
    assert data["auth_token"] == "secret-tok"


@pytest.mark.asyncio
async def test_naukri_discovery_adapter_normalization():
    adapter = NaukriDiscoveryAdapter()
    jobs = await adapter.fetch_jobs(company="", fixture_path=Path("fixtures/discovery/naukri_jobs.json"))

    assert len(jobs) >= 2
    j1 = next(j for j in jobs if j.external_id == "naukri-101")
    assert j1.platform == "naukri"
    assert "techcorp" in j1.company.lower()
    assert "senior python" in j1.title.lower()
    assert j1.salary is not None
    assert j1.salary.currency == "INR"
    assert j1.salary.min_amount == 2000000.0
    assert j1.salary.max_amount == 3000000.0
    assert j1.status == JobStatus.DISCOVERED


@pytest.mark.asyncio
async def test_naukri_cross_platform_deduplication():
    adapter = NaukriDiscoveryAdapter()
    jobs = await adapter.fetch_jobs(company="", fixture_path=Path("fixtures/discovery/naukri_jobs.json"))
    naukri_job = next(j for j in jobs if j.external_id == "naukri-101")

    # Create matching job on Greenhouse with identical canonical key
    from worker.discovery.models import Job
    from worker.discovery.normalization import compute_canonical_key, compute_content_hash

    gh_job = Job(
        id=uuid4(),
        platform="greenhouse",
        external_id="gh-dup-1",
        url="https://boards.greenhouse.io/techcorp/jobs/gh-dup-1",
        company=naukri_job.company,
        normalized_company=naukri_job.normalized_company,
        title=naukri_job.title,
        normalized_title=naukri_job.normalized_title,
        location=naukri_job.location,
        location_bucket=naukri_job.location_bucket,
        description=naukri_job.description,
        content_hash=naukri_job.content_hash,
        canonical_key=naukri_job.canonical_key,
        status=JobStatus.DISCOVERED,
    )

    match_result = await classify_duplicate_relationship(job_a=naukri_job, job_b=gh_job)
    assert match_result == DuplicateClassification.CROSS_PLATFORM_EXACT


@pytest.mark.asyncio
async def test_naukri_provider_form_inspection_and_l0_fill(mock_profile, tmp_path):
    provider = NaukriProvider()
    fixture_path = Path("fixtures/forms/naukri_job.html")
    assert fixture_path.exists()

    html = fixture_path.read_text(encoding="utf-8")

    # Mock page object for offline inspection
    class MockPage:
        async def content(self):
            return html

        async def screenshot(self, path):
            Path(path).write_bytes(b"mock_screenshot")

    page = MockPage()
    res = await provider.inspect_and_fill(
        page=page,
        profile=mock_profile,
        dry_run=True,
        screenshot_dir=tmp_path / "evidence",
    )

    assert res.provider == "naukri"
    assert res.submit_attempted is False  # MUST BE FALSE
    assert res.success is True

    # Check truthful profile values filled
    assert "Full Name *" in res.fields_filled
    assert res.fields_filled["Full Name *"] == "Jane Doe"
    assert "Email Address *" in res.fields_filled
    assert res.fields_filled["Email Address *"] == "jane.doe@example.com"
    assert "Mobile Number *" in res.fields_filled
    assert res.fields_filled["Mobile Number *"] == "+919876543210"

    # Required fields discovered
    discovered_labels = [f.label for f in res.discovered_fields]
    assert "Total Experience *" in discovered_labels
    assert "Current Location *" in discovered_labels


@pytest.mark.asyncio
async def test_naukri_provider_rejects_real_submit(mock_profile):
    provider = NaukriProvider()

    class MockPage:
        async def content(self):
            return "<html></html>"

    with pytest.raises(RealSubmitGateBlockedError, match="Real submissions on Naukri are strictly disabled"):
        await provider.inspect_and_fill(page=MockPage(), profile=mock_profile, dry_run=False)


def test_navigation_guard_permits_naukri_domains():
    guard = NavigationGuard()
    # Verified domain allowed
    val_url = guard.validate_url("https://www.naukri.com/job-listings-123")
    assert "www.naukri.com" in val_url

    val_base = guard.validate_url("https://naukri.com/job-listings-123")
    assert "naukri.com" in val_base

    # Untrusted domain rejected
    with pytest.raises(UnsupportedDestinationError):
        guard.validate_url("https://malicious-naukri.com/job")
