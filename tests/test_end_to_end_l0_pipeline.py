"""End-to-End L0 dry-run integration pipeline test (Phase 2.0).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 11, 12, 13, 14)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock
from playwright.async_api import async_playwright

from worker.answers.models import ResolutionStatus
from worker.answers.repository import InMemoryAnswerBankRepository
from worker.answers.resolver import AnswerResolver
from worker.application.models import (
    Application,
    ApplicationStatus,
    ApprovalStatus,
    AutonomyLevel,
)
from worker.application.orchestrator import ApplicationOrchestrator
from worker.application.outcomes import OutcomeMilestone, OutcomeTracker
from worker.application.repository import (
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)
from worker.core.caps import CapsEnforcer, InMemoryApplicationLedger
from worker.core.exceptions import RealSubmitGateBlockedError
from worker.core.kill_switch import InMemoryKillSwitch
from worker.core.runner import JobApplicationRunner
from worker.core.safety import SafetyEngine
from worker.discovery.models import JobStatus
from worker.matching.embedding import DeterministicFallbackEmbeddingProvider
from worker.matching.service import JobMatchingService
from worker.ops.approval import ApprovalManager
from worker.policy.engine import PolicyEngine
from worker.profile.devleveler import DevLevelerProfileSource
from worker.profile.models import (
    CandidateDetails,
    CandidatePreferences,
    EducationEntry,
    ExperienceEntry,
    ProfileSnapshot,
    SkillEntry,
)
from worker.providers.greenhouse import parse_greenhouse_form_html
from worker.providers.registry import create_default_registry


@pytest.fixture
def integrated_profile() -> ProfileSnapshot:
    return ProfileSnapshot(
        schema_version=1,
        profile_version="v2.0-rc-verified",
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
            skills=[
                SkillEntry(name="Python", years=6.0),
                SkillEntry(name="PostgreSQL", years=5.0),
                SkillEntry(name="Kubernetes", years=4.0),
            ],
            experience=[
                ExperienceEntry(
                    title="Staff Backend Engineer",
                    company="Global Tech",
                    location="Bangalore",
                    start_date="2021-01",
                    is_current=True,
                    highlights=["Architected high-throughput microservices in Python."],
                )
            ],
            education=[
                EducationEntry(
                    degree="B.Tech",
                    field_of_study="Computer Science",
                    institution="National University",
                    start_date="2016-08",
                    end_date="2020-05",
                )
            ],
        ),
        preferences=CandidatePreferences(
            roles=["Backend Engineer", "Platform Engineer"],
            locations=["Bangalore", "Remote"],
            work_modes=["remote", "hybrid"],
            levels=["Senior", "Staff"],
        ),
    )


@pytest.mark.asyncio
async def test_full_end_to_end_l0_dry_run_pipeline(tmp_path: Path, integrated_profile: ProfileSnapshot):
    # 1. Profile Source Setup
    cache_path = tmp_path / "devleveler_cache.json"
    mock_fb = AsyncMock()
    mock_fb.get_snapshot = AsyncMock(return_value=integrated_profile)
    profile_source = DevLevelerProfileSource(cache_path=cache_path, fallback_source=mock_fb)
    snapshot = await profile_source.get_snapshot()
    assert snapshot.candidate.name == "Kartik Shukla"

    # 2. Provider Registry and Discovery Setup
    registry = create_default_registry()
    gh_adapter = registry.get_discovery_adapter("greenhouse")
    gh_fixture = json.loads(Path("fixtures/discovery/greenhouse_jobs.json").read_text(encoding="utf-8"))
    target_job = gh_adapter.normalize_job_record(gh_fixture["jobs"][0], board_token="acme", company_name="Acme Corp")
    assert target_job is not None
    target_job.posted_at = datetime.now(timezone.utc)
    assert target_job.platform == "greenhouse"

    # 3. Matching and Scoring
    matching_service = JobMatchingService(
        embedding_provider=DeterministicFallbackEmbeddingProvider(),
    )
    from worker.matching.models import JobMatchRequest
    match_result = await matching_service.match_job(
        JobMatchRequest(job=target_job, profile=integrated_profile)
    )
    assert match_result.passed_hard_filters is True
    assert match_result.score > 40.0

    # 4. State Machine Repositories & Safety Engine
    from services.api.config import CapsConfig
    app_repo = InMemoryApplicationRepository()
    event_repo = InMemoryApplicationEventRepository()
    kill_switch = InMemoryKillSwitch(initial_enabled=True)
    caps_enforcer = CapsEnforcer(ledger=InMemoryApplicationLedger(), config=CapsConfig())
    safety_engine = SafetyEngine(
        kill_switch=kill_switch,
        caps_enforcer=caps_enforcer,
        real_submit_gate_enabled=False,
    )
    runner = JobApplicationRunner(safety_engine=safety_engine, profile_source=profile_source)

    orchestrator = ApplicationOrchestrator(
        application_repo=app_repo,
        event_repo=event_repo,
        safety_engine=safety_engine,
        runner=runner,
        matching_service=matching_service,
    )

    # 5. Create Application
    user_id = uuid4()
    app, created = await orchestrator.create_or_get_application(
        user_id=user_id,
        job=target_job,
        profile_snapshot=snapshot,
    )
    assert created is True
    assert app.status == ApplicationStatus.DISCOVERED

    # 6. Lifecycle Transitions
    matched_app = await orchestrator.evaluate_matching(
        application_id=app.id,
        job=target_job,
        profile_snapshot=snapshot,
    )
    assert matched_app.status == ApplicationStatus.MATCHED

    awaiting_app = await orchestrator.verify_eligibility(
        application_id=app.id,
        provider_name="greenhouse",
        company=target_job.company,
    )
    assert awaiting_app.status == ApplicationStatus.AWAITING_APPROVAL

    # 7. Human Approval via ApprovalManager
    approval_mgr = ApprovalManager(
        orchestrator=orchestrator,
        application_repo=app_repo,
        event_repo=event_repo,
        default_ttl_hours=24,
    )
    approved_app = await approval_mgr.approve_application(app.id, user_id=user_id, actor="owner")
    assert approved_app.status == ApplicationStatus.FILLING
    assert approved_app.approval_status == ApprovalStatus.APPROVED

    # 8. Form Inspection via parse_form_html & Provider
    gh_provider = registry.get_provider("greenhouse")
    fixture_path = Path("fixtures/forms/greenhouse_job.html").resolve()
    assert fixture_path.exists()
    html_content = fixture_path.read_text(encoding="utf-8")

    discovered_fields = parse_greenhouse_form_html(html_content, profile=snapshot)
    assert len(discovered_fields) >= 5

    # 9. L0 Dry-Run Form Execution via Central Orchestrator & Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(fixture_path.as_uri())

        completed_app = await orchestrator.execute_dry_run(
            application_id=approved_app.id,
            user_id=user_id,
            job_url_or_path=fixture_path.as_uri(),
            company="Acme Corp",
            provider_name="greenhouse",
            page=page,
        )
        assert completed_app.status == ApplicationStatus.DRY_RUN_DONE
        assert completed_app.fields_filled is not None
        await browser.close()

    # 10. Verify Real Submit Barrier Fails Closed
    with pytest.raises(RealSubmitGateBlockedError, match="real_submit_gate_enabled = False"):
        await gh_provider.submit_application(MagicMock())

    # 11. Post-Application Outcome Tracking
    outcome_file = tmp_path / "test_outcomes.json"
    outcome_tracker = OutcomeTracker(storage_path=outcome_file)
    outcome_record = outcome_tracker.record_milestone(
        application_id=str(app.id),
        milestone=OutcomeMilestone.INTERVIEW_SCHEDULED,
        event_timestamp=datetime.now(timezone.utc),
        notes="Hiring Manager Screening Call",
    )
    assert outcome_record.milestone == OutcomeMilestone.INTERVIEW_SCHEDULED
    records = outcome_tracker.get_outcomes_for_application(str(app.id))
    assert len(records) == 1
