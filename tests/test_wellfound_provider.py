"""Unit tests for Wellfound provider adapter, discovery, and session management (Phase 1.7).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 11, 12)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock

from worker.browser.exceptions import UnsupportedDestinationError
from worker.browser.navigation_guard import NavigationGuard
from worker.core.exceptions import RealSubmitGateBlockedError
from worker.discovery.models import JobStatus
from worker.profile.models import (
    CandidateDetails,
    CandidatePreferences,
    EducationEntry,
    ExperienceEntry,
    ProfileSnapshot,
    SkillEntry,
)
from worker.providers.wellfound import (
    WellfoundDiscoveryAdapter,
    WellfoundProvider,
    WellfoundSessionManager,
    WellfoundSessionStatus,
)


@pytest.fixture
def sample_profile() -> ProfileSnapshot:
    return ProfileSnapshot(
        schema_version=1,
        profile_version="v1.0-test",
        candidate=CandidateDetails(
            name="Kartik Shukla",
            email="kartik@example.com",
            phone="+919876543210",
            location="Bangalore, India",
            links={
                "github": "https://github.com/kartik",
                "linkedin": "https://linkedin.com/in/kartik",
                "website": "https://kartik.dev",
            },
            skills=[SkillEntry(name="Python", years=5.0)],
            experience=[
                ExperienceEntry(
                    title="Senior Backend Engineer",
                    company="Acme Corp",
                    location="Bangalore",
                    start_date="2022-01-01",
                    is_current=True,
                    highlights=["Designed microservices"],
                )
            ],
            education=[
                EducationEntry(
                    degree="B.Tech",
                    field_of_study="Computer Science",
                    institution="National University",
                    start_date="2016-08-01",
                    end_date="2020-05-30",
                )
            ],
        ),
        preferences=CandidatePreferences(
            roles=["Backend Engineer"],
            locations=["Bangalore", "Remote"],
            work_modes=["remote"],
            levels=["Senior", "Staff"],
        ),
    )


def test_wellfound_session_manager(tmp_path: Path):
    sess_file = tmp_path / "wellfound_cookies.json"
    mgr = WellfoundSessionManager(session_path=sess_file)

    assert mgr.check_session_status() == WellfoundSessionStatus.LOGIN_REQUIRED

    # Saving session
    mgr.save_session(
        cookies=[{"name": "wf_auth", "value": "token_123", "domain": ".wellfound.com"}],
        user_identifier="kartik@example.com",
    )
    assert mgr.check_session_status() == WellfoundSessionStatus.LOGGED_IN

    # Rejects password
    with pytest.raises(ValueError, match="Security violation"):
        mgr.save_session(
            cookies=[{"name": "password", "value": "secret123"}],
            user_identifier="test",
        )


def test_wellfound_discovery_adapter_normalization():
    adapter = WellfoundDiscoveryAdapter()
    fixture_path = Path("fixtures/discovery/wellfound_jobs.json")
    assert fixture_path.exists()

    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    jobs = adapter.parse_job_list(data["jobs"])

    assert len(jobs) == 2
    j1, j2 = jobs[0], jobs[1]

    assert j1.platform == "wellfound"
    assert j1.external_id == "wf-8901"
    assert j1.company == "Stealth AI"
    assert j1.status == JobStatus.DISCOVERED
    assert j1.salary is not None
    assert j1.salary.min_amount == 140000.0
    assert j1.salary.max_amount == 180000.0

    # Test already-applied detection
    assert j2.status == JobStatus.APPLIED
    assert j2.metadata["already_applied"] is True


@pytest.mark.asyncio
async def test_wellfound_provider_form_inspection_and_l0_fill(sample_profile: ProfileSnapshot):
    provider = WellfoundProvider()
    fixture_path = Path("fixtures/forms/wellfound_job.html")
    assert fixture_path.exists()
    html_content = fixture_path.read_text(encoding="utf-8")

    mock_page = MagicMock()
    mock_page.content = AsyncMock(return_value=html_content)

    # 1. Inspect form
    fields = await provider.inspect_form(mock_page)
    assert len(fields) >= 7

    names = {f.name for f in fields}
    assert "firstName" in names
    assert "lastName" in names
    assert "email" in names
    assert "phone" in names

    # 2. Fill form (L0 dry run)
    result = await provider.fill_form(
        page=mock_page,
        profile=sample_profile,
        fields=fields,
    )

    assert result.fields_filled.get("First Name *") == "Kartik"
    assert result.fields_filled.get("Last Name *") == "Shukla"
    assert result.fields_filled.get("Email *") == "kartik@example.com"
    assert result.fields_filled.get("Phone *") == "+919876543210"

    # Notice period requires user input / unresolved
    assert "Notice Period (Days) *" in result.unresolved_fields


@pytest.mark.asyncio
async def test_wellfound_provider_rejects_real_submit():
    provider = WellfoundProvider()
    mock_page = MagicMock()

    with pytest.raises(RealSubmitGateBlockedError, match="real_submit_gate_enabled = False"):
        await provider.submit_application(mock_page)


def test_navigation_guard_permits_wellfound_domains():
    guard = NavigationGuard()
    assert "wellfound.com" in guard.validate_url("https://wellfound.com/jobs/8901")
    assert "www.wellfound.com" in guard.validate_url("https://www.wellfound.com/jobs/8901")
    assert "angel.co" in guard.validate_url("https://angel.co/company/stealth/jobs/8901")
    with pytest.raises(UnsupportedDestinationError):
        guard.validate_url("https://malicious-wellfound.com/jobs")
