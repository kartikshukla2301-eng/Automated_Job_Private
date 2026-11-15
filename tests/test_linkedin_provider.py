"""Unit tests for Restricted LinkedIn Provider Adapter, Discovery, and Autonomy Constraints (Phase 1.8).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 9, 10, 11, 12)
- docs/BUILD_RULES.md
"""

import json
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock

from worker.application.models import AutonomyLevel
from worker.browser.exceptions import UnsupportedDestinationError
from worker.browser.navigation_guard import NavigationGuard
from worker.core.exceptions import RealSubmitGateBlockedError
from worker.discovery.models import JobStatus
from worker.ops.autonomy import AutonomyController
from worker.profile.models import (
    CandidateDetails,
    CandidatePreferences,
    EducationEntry,
    ExperienceEntry,
    ProfileSnapshot,
    SkillEntry,
)
from worker.providers.linkedin import (
    LinkedInDiscoveryAdapter,
    LinkedInLoginWallError,
    LinkedInProvider,
    LinkedInSecurityCheckpointError,
    LinkedInSessionManager,
    LinkedInSessionStatus,
    detect_security_checkpoint_or_wall,
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
                    title="Senior Distributed Systems Engineer",
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
            roles=["Distributed Systems Engineer"],
            locations=["Bangalore", "Remote"],
            work_modes=["remote"],
            levels=["Senior"],
        ),
    )


def test_linkedin_session_manager(tmp_path: Path):
    sess_file = tmp_path / "linkedin_cookies.json"
    mgr = LinkedInSessionManager(session_path=sess_file)

    assert mgr.check_session_status() == LinkedInSessionStatus.LOGIN_REQUIRED

    # Saving session
    mgr.save_session(
        cookies=[{"name": "li_at", "value": "auth_cookie_token_123", "domain": ".linkedin.com"}],
        user_identifier="kartik@example.com",
    )
    assert mgr.check_session_status() == LinkedInSessionStatus.LOGGED_IN

    # Rejects password
    with pytest.raises(ValueError, match="Security violation"):
        mgr.save_session(
            cookies=[{"name": "user_password", "value": "secret_pass"}],
            user_identifier="test",
        )


def test_checkpoint_and_login_wall_detection():
    # 1. Normal page passes
    detect_security_checkpoint_or_wall(
        url="https://www.linkedin.com/jobs/view/123",
        html_content="<html><body><div class='jobs-easy-apply'>Apply</div></body></html>",
    )

    # 2. Login wall detected
    with pytest.raises(LinkedInLoginWallError, match="authentication wall"):
        detect_security_checkpoint_or_wall(
            url="https://www.linkedin.com/authwall?trk=...",
            html_content="<html><body>Sign in to LinkedIn</body></html>",
        )

    # 3. Security checkpoint detected via URL
    with pytest.raises(LinkedInSecurityCheckpointError, match="security challenge"):
        detect_security_checkpoint_or_wall(
            url="https://www.linkedin.com/checkpoint/challenge/123",
            html_content="<html><body>Verify your identity</body></html>",
        )

    # 4. CAPTCHA detected via HTML content
    with pytest.raises(LinkedInSecurityCheckpointError, match="security challenge"):
        detect_security_checkpoint_or_wall(
            url="https://www.linkedin.com/jobs/view/123",
            html_content="<html><body>Please prove you're a human with recaptcha</body></html>",
        )


def test_linkedin_discovery_adapter_normalization():
    adapter = LinkedInDiscoveryAdapter()
    fixture_path = Path("fixtures/discovery/linkedin_jobs.json")
    assert fixture_path.exists()

    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    jobs = adapter.parse_job_list(data["jobs"])

    assert len(jobs) == 2
    j1, j2 = jobs[0], jobs[1]

    assert j1.platform == "linkedin"
    assert j1.external_id == "li-9801"
    assert j1.company == "ScaleOps Technologies"
    assert j1.status == JobStatus.DISCOVERED
    assert "trk" not in j1.url
    assert j1.metadata["easy_apply"] is True

    # Check already-applied detection
    assert j2.external_id == "li-9802"
    assert j2.status == JobStatus.APPLIED
    assert j2.metadata["already_applied"] is True


@pytest.mark.asyncio
async def test_linkedin_provider_form_inspection_and_l0_fill(sample_profile: ProfileSnapshot):
    provider = LinkedInProvider()
    fixture_path = Path("fixtures/forms/linkedin_job.html")
    assert fixture_path.exists()
    html_content = fixture_path.read_text(encoding="utf-8")

    mock_page = MagicMock()
    mock_page.url = "https://www.linkedin.com/jobs/view/9801"
    mock_page.content = AsyncMock(return_value=html_content)

    # 1. Inspect form
    fields = await provider.inspect_form(mock_page)
    assert len(fields) >= 5

    names = {f.name for f in fields}
    assert "firstName" in names
    assert "lastName" in names
    assert "emailAddress" in names
    assert "phoneNumber" in names

    # 2. Fill form (L0 dry-run)
    result = await provider.fill_form(
        page=mock_page,
        profile=sample_profile,
        fields=fields,
    )

    assert result.provider == "linkedin"
    assert result.fields_filled.get("First name *") == "Kartik"
    assert result.fields_filled.get("Last name *") == "Shukla"
    assert result.fields_filled.get("Email address *") == "kartik@example.com"
    assert result.fields_filled.get("Phone number *") == "+919876543210"

    assert "What is your notice period in days? *" in result.unresolved_fields


@pytest.mark.asyncio
async def test_linkedin_provider_stops_on_checkpoint():
    provider = LinkedInProvider()
    mock_page = MagicMock()
    mock_page.url = "https://www.linkedin.com/checkpoint/challenge/999"
    mock_page.content = AsyncMock(return_value="<html>Verify your identity</html>")

    with pytest.raises(LinkedInSecurityCheckpointError):
        await provider.inspect_form(mock_page)


@pytest.mark.asyncio
async def test_linkedin_provider_rejects_real_submit():
    provider = LinkedInProvider()
    mock_page = MagicMock()

    with pytest.raises(RealSubmitGateBlockedError, match="real_submit_gate_enabled = False"):
        await provider.submit_application(mock_page)


def test_navigation_guard_permits_linkedin_domains():
    guard = NavigationGuard()
    assert "www.linkedin.com" in guard.validate_url("https://www.linkedin.com/jobs/view/9801")
    assert "linkedin.com" in guard.validate_url("https://linkedin.com/jobs/view/9801")
    with pytest.raises(UnsupportedDestinationError):
        guard.validate_url("https://malicious-linkedin.com/jobs")


def test_linkedin_restricted_autonomy_enforcement():
    controller = AutonomyController()

    # Starts at L0
    assert controller.get_level("linkedin") == AutonomyLevel.L0

    # Can be set to L1 by owner
    controller.set_level_by_owner("linkedin", AutonomyLevel.L1)
    assert controller.get_level("linkedin") == AutonomyLevel.L1

    # Attempt to set to L2 or L3 fails with ValueError
    with pytest.raises(ValueError, match="LinkedIn is a restricted provider"):
        controller.set_level_by_owner("linkedin", AutonomyLevel.L2)

    with pytest.raises(ValueError, match="LinkedIn is a restricted provider"):
        controller.set_level_by_owner("linkedin", AutonomyLevel.L3)

    # Promotion evaluation from L1 to L2 is blocked
    report = controller.evaluate_eligibility(
        provider="linkedin",
        total_apps_at_level=50,
        reviewed_accuracy=100.0,
        wrong_sensitive_count=0,
        duplicate_count=0,
    )
    assert report.eligible_for_next_level is False
    assert any("restricted" in b.lower() for b in report.blocking_conditions)
