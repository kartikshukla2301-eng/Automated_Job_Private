"""Unit tests for Ashby job provider adapter, discovery, and form execution (Phase 1.7).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 11, 12)
- docs/BUILD_RULES.md
"""

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
from worker.providers.ashby import (
    AshbyDiscoveryAdapter,
    AshbyProvider,
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
            skills=[SkillEntry(name="Kubernetes", years=4.0)],
            experience=[
                ExperienceEntry(
                    title="Senior Platform Engineer",
                    company="Tech Corp",
                    location="Remote",
                    start_date="2022-01-01",
                    is_current=True,
                    highlights=["Managed Kubernetes clusters"],
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
            roles=["Platform Engineer"],
            locations=["San Francisco", "Remote"],
            work_modes=["remote"],
            levels=["Senior"],
        ),
    )


def test_ashby_discovery_adapter_normalization():
    adapter = AshbyDiscoveryAdapter()
    fixture_path = Path("fixtures/discovery/ashby_jobs.json")
    assert fixture_path.exists()

    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    jobs = adapter.parse_job_list(data["jobs"])

    assert len(jobs) == 2
    j1, j2 = jobs[0], jobs[1]

    assert j1.platform == "ashby"
    assert j1.external_id == "ashby-401"
    assert j1.company == "CloudScale Systems"
    assert j1.status == JobStatus.DISCOVERED
    assert j1.salary is not None
    assert j1.salary.min_amount == 160000.0
    assert j1.salary.max_amount == 195000.0

    assert j2.external_id == "ashby-402"
    assert j2.company == "CloudScale Systems"
    assert j2.salary is not None
    assert j2.salary.currency == "INR"
    assert j2.salary.min_amount == 2800000.0
    assert j2.salary.max_amount == 3500000.0


@pytest.mark.asyncio
async def test_ashby_provider_form_inspection_and_l0_fill(sample_profile: ProfileSnapshot):
    provider = AshbyProvider()
    fixture_path = Path("fixtures/forms/ashby_job.html")
    assert fixture_path.exists()
    html_content = fixture_path.read_text(encoding="utf-8")

    mock_page = MagicMock()
    mock_page.content = AsyncMock(return_value=html_content)

    # 1. Inspect form
    fields = await provider.inspect_form(mock_page)
    assert len(fields) >= 7

    names = {f.name for f in fields}
    assert "first_name" in names
    assert "last_name" in names
    assert "email" in names
    assert "phone" in names

    # 2. Fill form (L0 dry-run)
    result = await provider.fill_form(
        page=mock_page,
        profile=sample_profile,
        fields=fields,
    )

    assert result.fields_filled.get("First Name *") == "Kartik"
    assert result.fields_filled.get("Last Name *") == "Shukla"
    assert result.fields_filled.get("Email *") == "kartik@example.com"
    assert result.fields_filled.get("Phone Number *") == "+919876543210"

    assert "Notice Period (Days) *" in result.unresolved_fields


@pytest.mark.asyncio
async def test_ashby_provider_rejects_real_submit():
    provider = AshbyProvider()
    mock_page = MagicMock()

    with pytest.raises(RealSubmitGateBlockedError, match="real_submit_gate_enabled = False"):
        await provider.submit_application(mock_page)


def test_navigation_guard_permits_ashby_domains():
    guard = NavigationGuard()
    assert "jobs.ashbyhq.com" in guard.validate_url("https://jobs.ashbyhq.com/cloudscale/401")
    assert "ashbyhq.com" in guard.validate_url("https://ashbyhq.com/company/jobs")
    with pytest.raises(UnsupportedDestinationError):
        guard.validate_url("https://malicious-ashby.com/jobs")
