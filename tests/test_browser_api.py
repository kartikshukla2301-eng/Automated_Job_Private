"""Tests for Browser Form Inspection API endpoints (/api/v1/applications/{id}/inspect-form, fill-plan, evidence).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12, 13)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from services.api.config import CapsConfig, Settings
from services.api.dependencies import (
    get_application_event_repository,
    get_application_orchestrator,
    get_application_repository,
    get_browser_manager,
    get_navigation_guard,
    get_profile_source,
    get_safety_engine,
)
from services.api.main import create_app
from worker.application.models import Application, ApplicationStatus, AutonomyLevel
from worker.application.orchestrator import ApplicationOrchestrator
from worker.application.repository import (
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)
from worker.browser.browser_config import BrowserConfig
from worker.browser.browser_manager import BrowserManager
from worker.browser.navigation_guard import NavigationGuard
from worker.core.caps import CapsEnforcer, InMemoryApplicationLedger
from worker.core.kill_switch import InMemoryKillSwitch
from worker.core.runner import JobApplicationRunner
from worker.core.safety import SafetyEngine
from worker.matching.embedding import DeterministicFallbackEmbeddingProvider
from worker.matching.service import JobMatchingService
from worker.profile.localfile import LocalFileProfileSource
from worker.providers.greenhouse import GreenhouseProvider


@pytest.fixture
def clean_repos():
    app_repo = InMemoryApplicationRepository()
    event_repo = InMemoryApplicationEventRepository()
    return app_repo, event_repo


@pytest.fixture
def shared_browser_manager():
    return BrowserManager(config=BrowserConfig(headless=True))


@pytest.fixture
def test_app(clean_repos, shared_browser_manager: BrowserManager, tmp_path: Path):
    app_repo, event_repo = clean_repos
    ks = InMemoryKillSwitch(initial_enabled=True)
    ledger = InMemoryApplicationLedger()
    enforcer = CapsEnforcer(CapsConfig(global_per_day=20, per_company_per_day=5), ledger)
    safety_engine = SafetyEngine(
        kill_switch=ks,
        caps_enforcer=enforcer,
        real_submit_gate_enabled=False,
    )
    profile_source = LocalFileProfileSource(Path("fixtures/profile.yaml"))
    runner = JobApplicationRunner(
        safety_engine=safety_engine,
        profile_source=profile_source,
        providers={"greenhouse": GreenhouseProvider()},
        evidence_dir=tmp_path / "evidence",
    )
    matching_service = JobMatchingService(
        embedding_provider=DeterministicFallbackEmbeddingProvider(),
        threshold=65.0,
    )
    orchestrator = ApplicationOrchestrator(
        application_repo=app_repo,
        event_repo=event_repo,
        matching_service=matching_service,
        safety_engine=safety_engine,
        runner=runner,
    )

    dev_settings = Settings(allow_tokenless_dev=True, api_host="127.0.0.1")
    app = create_app(dev_settings)
    app.dependency_overrides[get_application_repository] = lambda: app_repo
    app.dependency_overrides[get_application_event_repository] = lambda: event_repo
    app.dependency_overrides[get_application_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_safety_engine] = lambda: safety_engine
    app.dependency_overrides[get_browser_manager] = lambda: shared_browser_manager
    app.dependency_overrides[get_navigation_guard] = lambda: NavigationGuard(fixtures_dir=Path("fixtures"))
    app.dependency_overrides[get_profile_source] = lambda: profile_source
    return app


@pytest.fixture
def client(test_app) -> TestClient:
    return TestClient(test_app)


@pytest.mark.asyncio
async def test_api_inspect_form_success(client: TestClient, clean_repos):
    """Verify POST /inspect-form inspects page safely and returns FillPlanResponse."""
    app_repo, _ = clean_repos
    app_id = uuid4()
    user_id = uuid4()
    app = Application(
        id=app_id,
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-insp-1",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.READY,
        idempotency_key="key-insp-1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await app_repo.create(app)

    response = client.post(
        f"/api/v1/applications/{app_id}/inspect-form",
        json={
            "user_id": str(user_id),
            "job_url_or_path": "fixtures/forms/greenhouse_job.html",
            "company": "Example Software",
            "provider_name": "greenhouse",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_url"] == "fixtures/forms/greenhouse_job.html"
    assert data["total_fields"] >= 8
    assert data["auto_approved_count"] >= 3
    assert data["blocked_count"] >= 1
    assert len(data["fields"]) >= 8


@pytest.mark.asyncio
async def test_api_inspect_form_rejects_unsupported_destination(client: TestClient, clean_repos):
    """Verify attempting to inspect an unapproved origin returns 400 Bad Request."""
    app_repo, _ = clean_repos
    app_id = uuid4()
    user_id = uuid4()
    app = Application(
        id=app_id,
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-insp-2",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.READY,
        idempotency_key="key-insp-2",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await app_repo.create(app)

    response = client.post(
        f"/api/v1/applications/{app_id}/inspect-form",
        json={
            "user_id": str(user_id),
            "job_url_or_path": "https://malicious.evil.com/apply",
            "company": "Evil Corp",
        },
    )
    assert response.status_code == 400
    assert "Navigation blocked to unsupported destination" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_inspect_form_user_mismatch_forbidden(client: TestClient, clean_repos):
    """Verify another user cannot trigger inspection for an application."""
    app_repo, _ = clean_repos
    app_id = uuid4()
    owner_user_id = uuid4()
    other_user_id = uuid4()
    app = Application(
        id=app_id,
        user_id=owner_user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-insp-3",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.READY,
        idempotency_key="key-insp-3",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await app_repo.create(app)

    response = client.post(
        f"/api/v1/applications/{app_id}/inspect-form",
        json={
            "user_id": str(other_user_id),
            "company": "Example Software",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_api_get_fill_plan_and_evidence(client: TestClient, clean_repos):
    """Verify GET /fill-plan and GET /evidence return structured artifacts after inspection."""
    app_repo, _ = clean_repos
    app_id = uuid4()
    user_id = uuid4()
    app = Application(
        id=app_id,
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-insp-4",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.READY,
        idempotency_key="key-insp-4",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await app_repo.create(app)

    # 1. Before inspection: 404
    resp_plan_before = client.get(f"/api/v1/applications/{app_id}/fill-plan")
    assert resp_plan_before.status_code == 404

    resp_ev_before = client.get(f"/api/v1/applications/{app_id}/evidence")
    assert resp_ev_before.status_code == 404

    # 2. Run inspection
    inspect_resp = client.post(
        f"/api/v1/applications/{app_id}/inspect-form",
        json={
            "user_id": str(user_id),
            "job_url_or_path": "fixtures/forms/greenhouse_job.html",
            "company": "Example Software",
        },
    )
    assert inspect_resp.status_code == 200

    # 3. After inspection: GET /fill-plan returns 200
    resp_plan_after = client.get(f"/api/v1/applications/{app_id}/fill-plan")
    assert resp_plan_after.status_code == 200
    assert resp_plan_after.json()["total_fields"] >= 8

    # 4. After inspection: GET /evidence returns 200
    resp_ev_after = client.get(f"/api/v1/applications/{app_id}/evidence")
    assert resp_ev_after.status_code == 200
    assert resp_ev_after.json()["outcome"] == "L0_INSPECTION_COMPLETED"
    assert resp_ev_after.json()["screenshot_path"] is not None
