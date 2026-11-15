"""Integration tests for central ApplicationOrchestrator, safety gates, and dry-run execution.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 13, 14, 15)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from worker.application.exceptions import (
    ApprovalRequiredError,
)
from worker.application.models import (
    ApplicationStatus,
    ApprovalStatus,
    AutonomyLevel,
)
from worker.application.orchestrator import ApplicationOrchestrator
from worker.application.repository import (
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)
from worker.core.caps import CapsConfig, CapsEnforcer, InMemoryApplicationLedger
from worker.core.kill_switch import InMemoryKillSwitch
from worker.core.runner import JobApplicationRunner
from worker.core.safety import SafetyEngine
from worker.discovery.models import Job, JobStatus, SalaryInfo
from worker.matching.embedding import DeterministicFallbackEmbeddingProvider
from worker.matching.models import CandidateJobPreferences
from worker.matching.service import JobMatchingService
from worker.profile.localfile import LocalFileProfileSource
from worker.profile.models import ProfileSnapshot
from worker.providers.greenhouse import GreenhouseProvider


@pytest.fixture
def profile_snapshot() -> ProfileSnapshot:
    source = LocalFileProfileSource("fixtures/profile.yaml")
    return source.load_snapshot()


@pytest.fixture
def sample_job() -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        platform="greenhouse",
        external_id="gh-orch-101",
        canonical_key="example_software:software_engineer:remote",
        company="Example Software",
        normalized_company="example software",
        title="Software Engineer",
        normalized_title="software engineer",
        url="fixtures/forms/greenhouse_job.html",
        description="Looking for Software Engineer with Python and React experience.",
        location="Remote",
        location_bucket="remote",
        employment_type="Full-time",
        posted_at=now - timedelta(hours=1),
        first_seen_at=now - timedelta(hours=1),
        content_hash="e" * 64,
        status=JobStatus.DISCOVERED,
    )


@pytest.fixture
def orchestrator_setup(tmp_path):
    app_repo = InMemoryApplicationRepository()
    event_repo = InMemoryApplicationEventRepository()
    matching_service = JobMatchingService(
        embedding_provider=DeterministicFallbackEmbeddingProvider(),
        threshold=65.0,
    )
    kill_switch = InMemoryKillSwitch(initial_enabled=True)
    caps_config = CapsConfig(global_per_day=20, per_company_per_day=2)
    caps_enforcer = CapsEnforcer(caps_config, InMemoryApplicationLedger())
    safety_engine = SafetyEngine(
        kill_switch=kill_switch,
        caps_enforcer=caps_enforcer,
        real_submit_gate_enabled=False,
    )
    profile_source = LocalFileProfileSource("fixtures/profile.yaml")
    evidence_dir = tmp_path / "evidence"
    runner = JobApplicationRunner(
        safety_engine=safety_engine,
        profile_source=profile_source,
        providers={"greenhouse": GreenhouseProvider()},
        evidence_dir=evidence_dir,
    )

    orch = ApplicationOrchestrator(
        application_repo=app_repo,
        event_repo=event_repo,
        matching_service=matching_service,
        safety_engine=safety_engine,
        runner=runner,
    )

    return orch, app_repo, event_repo, kill_switch, caps_enforcer


@pytest.mark.asyncio
async def test_orchestrator_create_application_idempotent(orchestrator_setup, sample_job, profile_snapshot):
    orch, app_repo, event_repo, _, _ = orchestrator_setup
    user_id = uuid4()

    app1, created1 = await orch.create_or_get_application(user_id, sample_job, profile_snapshot)
    assert created1 is True
    assert app1.status == ApplicationStatus.DISCOVERED

    # Calling again returns same application idempotently
    app2, created2 = await orch.create_or_get_application(user_id, sample_job, profile_snapshot)
    assert created2 is False
    assert app2.id == app1.id


@pytest.mark.asyncio
async def test_orchestrator_full_lifecycle_l0_dry_run(orchestrator_setup, sample_job, profile_snapshot):
    orch, app_repo, event_repo, _, _ = orchestrator_setup
    user_id = uuid4()

    # Step 1: Create -> DISCOVERED
    app, created = await orch.create_or_get_application(user_id, sample_job, profile_snapshot)
    assert app.status == ApplicationStatus.DISCOVERED

    # Step 2: Match -> MATCHED
    prefs = CandidateJobPreferences(
        roles=["Software Engineer"],
        required_skills=["Python"],
        work_modes=["remote"],
    )
    matched_app = await orch.evaluate_matching(app.id, sample_job, profile_snapshot, preferences=prefs)
    assert matched_app.status == ApplicationStatus.MATCHED
    assert matched_app.score is not None
    assert matched_app.score >= 65.0

    # Step 3: Eligibility & Safety -> ELIGIBLE -> READY -> AWAITING_APPROVAL
    awaiting_app = await orch.verify_eligibility(matched_app.id, provider_name="greenhouse", company=sample_job.company)
    assert awaiting_app.status == ApplicationStatus.AWAITING_APPROVAL
    assert awaiting_app.approval_status == ApprovalStatus.PENDING

    # Step 4: User Approval Gate -> FILLING
    filling_app = await orch.approve(awaiting_app.id, user_id=user_id)
    assert filling_app.status == ApplicationStatus.FILLING
    assert filling_app.approval_status == ApprovalStatus.APPROVED

    # Step 5: Execute L0 Dry Run -> DRY_RUN_DONE
    done_app = await orch.execute_dry_run(
        application_id=filling_app.id,
        user_id=user_id,
        job_url_or_path="fixtures/forms/greenhouse_job.html",
        company=sample_job.company,
        provider_name="greenhouse",
    )

    assert done_app.status == ApplicationStatus.DRY_RUN_DONE
    assert done_app.evidence_ref is not None
    assert len(done_app.fields_filled) > 0
    assert done_app.applied_at is None  # L0 never sets applied_at!

    # Audit events verified
    events = await event_repo.list_by_application_id(app.id)
    event_types = [e.event_type for e in events]
    assert "CREATED" in event_types
    assert "STATE_TRANSITION" in event_types
    assert "DRY_RUN_STARTED" in event_types


@pytest.mark.asyncio
async def test_orchestrator_matching_rejection(orchestrator_setup, sample_job, profile_snapshot):
    orch, _, _, _, _ = orchestrator_setup
    user_id = uuid4()
    app, _ = await orch.create_or_get_application(user_id, sample_job, profile_snapshot)

    # Preferences completely unrelated to job
    prefs = CandidateJobPreferences(
        roles=["Pediatric Nurse"],
        required_skills=["Nursing", "Triage"],
        work_modes=["onsite"],
    )
    rejected_app = await orch.evaluate_matching(app.id, sample_job, profile_snapshot, preferences=prefs)
    assert rejected_app.status == ApplicationStatus.REJECTED


@pytest.mark.asyncio
async def test_orchestrator_safety_barrier_blocks_when_kill_switch_active(orchestrator_setup, sample_job, profile_snapshot):
    orch, _, _, kill_switch, _ = orchestrator_setup
    user_id = uuid4()
    app, _ = await orch.create_or_get_application(user_id, sample_job, profile_snapshot)
    matched_app = await orch.evaluate_matching(app.id, sample_job, profile_snapshot)

    # Trip kill switch before eligibility check
    kill_switch.trip(reason="Emergency maintenance")

    blocked_app = await orch.verify_eligibility(matched_app.id, provider_name="greenhouse", company=sample_job.company)
    assert blocked_app.status == ApplicationStatus.BLOCKED


@pytest.mark.asyncio
async def test_orchestrator_safety_barrier_blocks_when_daily_cap_exceeded(orchestrator_setup, sample_job, profile_snapshot):
    orch, _, _, _, caps_enforcer = orchestrator_setup
    user_id = uuid4()
    app, _ = await orch.create_or_get_application(user_id, sample_job, profile_snapshot)
    matched_app = await orch.evaluate_matching(app.id, sample_job, profile_snapshot)

    # Override caps to 0
    caps_enforcer.config.global_per_day = 0

    blocked_app = await orch.verify_eligibility(matched_app.id, provider_name="greenhouse", company=sample_job.company)
    assert blocked_app.status == ApplicationStatus.BLOCKED


@pytest.mark.asyncio
async def test_orchestrator_unapproved_cannot_execute_dry_run(orchestrator_setup, sample_job, profile_snapshot):
    orch, _, _, _, _ = orchestrator_setup
    user_id = uuid4()
    app, _ = await orch.create_or_get_application(user_id, sample_job, profile_snapshot)
    matched_app = await orch.evaluate_matching(app.id, sample_job, profile_snapshot)
    awaiting_app = await orch.verify_eligibility(matched_app.id, provider_name="greenhouse", company=sample_job.company)

    # Attempting dry-run while still in AWAITING_APPROVAL raises ApprovalRequiredError
    with pytest.raises(ApprovalRequiredError):
        await orch.execute_dry_run(
            application_id=awaiting_app.id,
            user_id=user_id,
            job_url_or_path="fixtures/forms/greenhouse_job.html",
            company=sample_job.company,
        )


@pytest.mark.asyncio
async def test_orchestrator_user_reject_at_approval_gate(orchestrator_setup, sample_job, profile_snapshot):
    orch, _, _, _, _ = orchestrator_setup
    user_id = uuid4()
    app, _ = await orch.create_or_get_application(user_id, sample_job, profile_snapshot)
    matched_app = await orch.evaluate_matching(app.id, sample_job, profile_snapshot)
    awaiting_app = await orch.verify_eligibility(matched_app.id, provider_name="greenhouse", company=sample_job.company)

    rejected_app = await orch.reject(awaiting_app.id, user_id=user_id, reason="User not interested")
    assert rejected_app.status == ApplicationStatus.REJECTED
    assert rejected_app.approval_status == ApprovalStatus.REJECTED


@pytest.mark.asyncio
async def test_orchestrator_interrupted_filling_recovery(orchestrator_setup, sample_job, profile_snapshot):
    orch, app_repo, event_repo, _, _ = orchestrator_setup
    user_id = uuid4()
    app, _ = await orch.create_or_get_application(user_id, sample_job, profile_snapshot)

    # Simulate application that was in FILLING status when worker process abruptly crashed
    filling_app = app.model_copy(update={"status": ApplicationStatus.FILLING})
    await app_repo.update(filling_app)

    # Recovery must NOT blindly replay submission; transitions safely to FAILED with manual retry
    recovered_app = await orch.recover_interrupted_application(filling_app.id, reason="Server crashed during filling")
    assert recovered_app.status == ApplicationStatus.FAILED
    assert "Server crashed during filling" in recovered_app.error

    events = await event_repo.list_by_application_id(app.id)
    event_types = [e.event_type for e in events]
    assert "RECOVERY_INITIATED" in event_types
