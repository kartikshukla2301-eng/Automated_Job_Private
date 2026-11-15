"""Tests for Application Lifecycle API routes (/api/v1/applications/*)."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.api.config import CapsConfig, Settings
from services.api.dependencies import (
    get_application_event_repository,
    get_application_orchestrator,
    get_application_repository,
    get_runner,
    get_safety_engine,
)
from services.api.main import create_app
from worker.application.models import (
    Application,
    ApplicationEvent,
    ApplicationEventType,
    ApplicationStatus,
    ApprovalStatus,
    AutonomyLevel,
)
from worker.application.orchestrator import ApplicationOrchestrator
from worker.application.repository import (
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)
from worker.core.caps import CapsEnforcer, InMemoryApplicationLedger
from worker.core.kill_switch import InMemoryKillSwitch
from worker.core.runner import JobApplicationRunner
from worker.core.safety import SafetyEngine
from worker.matching.embedding import DeterministicFallbackEmbeddingProvider
from worker.matching.service import JobMatchingService
from worker.profile.localfile import LocalFileProfileSource
from worker.providers.greenhouse import GreenhouseProvider


@pytest.fixture
def clean_repos(tmp_path: Path):
    app_repo = InMemoryApplicationRepository()
    event_repo = InMemoryApplicationEventRepository()
    return app_repo, event_repo


@pytest.fixture
def mock_safety_engine() -> SafetyEngine:
    ks = InMemoryKillSwitch(initial_enabled=True)
    ledger = InMemoryApplicationLedger()
    enforcer = CapsEnforcer(CapsConfig(global_per_day=20, per_company_per_day=5), ledger)
    return SafetyEngine(
        kill_switch=ks,
        caps_enforcer=enforcer,
        real_submit_gate_enabled=False,
    )


@pytest.fixture
def orchestrator(clean_repos, mock_safety_engine: SafetyEngine, tmp_path: Path) -> ApplicationOrchestrator:
    app_repo, event_repo = clean_repos
    profile_source = LocalFileProfileSource(Path("fixtures/profile.yaml"))
    runner = JobApplicationRunner(
        safety_engine=mock_safety_engine,
        profile_source=profile_source,
        providers={"greenhouse": GreenhouseProvider()},
        evidence_dir=tmp_path / "evidence",
    )
    matching_service = JobMatchingService(
        embedding_provider=DeterministicFallbackEmbeddingProvider(),
        threshold=65.0,
    )
    return ApplicationOrchestrator(
        application_repo=app_repo,
        event_repo=event_repo,
        matching_service=matching_service,
        safety_engine=mock_safety_engine,
        runner=runner,
    )


@pytest.fixture
def test_app(clean_repos, orchestrator: ApplicationOrchestrator, mock_safety_engine: SafetyEngine):
    app_repo, event_repo = clean_repos
    dev_settings = Settings(allow_tokenless_dev=True, api_host="127.0.0.1")
    app = create_app(dev_settings)
    app.dependency_overrides[get_application_repository] = lambda: app_repo
    app.dependency_overrides[get_application_event_repository] = lambda: event_repo
    app.dependency_overrides[get_application_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_safety_engine] = lambda: mock_safety_engine
    return app


@pytest.fixture
def client(test_app) -> TestClient:
    return TestClient(test_app)


def test_api_get_application_not_found(client: TestClient):
    """Verify 404 is returned for non-existent application."""
    random_id = uuid.uuid4()
    response = client.get(f"/api/v1/applications/{random_id}")
    assert response.status_code == 404
    assert f"Application '{random_id}' not found." in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_get_application_success(client: TestClient, clean_repos):
    """Verify application details are retrieved correctly."""
    app_repo, _ = clean_repos
    app_id = uuid.uuid4()
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()
    app = Application(
        id=app_id,
        user_id=user_id,
        job_id=job_id,
        platform="greenhouse",
        external_id="ext-101",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.DISCOVERED,
        idempotency_key="token-test-101",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await app_repo.create(app)

    response = client.get(f"/api/v1/applications/{app_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(app_id)
    assert data["user_id"] == str(user_id)
    assert data["job_id"] == str(job_id)
    assert data["status"] == "DISCOVERED"
    assert data["platform"] == "greenhouse"
    assert data["idempotency_key"] == "token-test-101"


@pytest.mark.asyncio
async def test_api_get_application_events(client: TestClient, clean_repos):
    """Verify audit events are returned chronologically."""
    _, event_repo = clean_repos
    app_id = uuid.uuid4()
    event1 = ApplicationEvent(
        id=uuid.uuid4(),
        application_id=app_id,
        event_type=ApplicationEventType.STATE_TRANSITION,
        previous_status=ApplicationStatus.DISCOVERED,
        new_status=ApplicationStatus.MATCHED,
        reason="Match completed",
        triggering_component="ApplicationOrchestrator",
        timestamp=datetime.now(timezone.utc),
    )
    event2 = ApplicationEvent(
        id=uuid.uuid4(),
        application_id=app_id,
        event_type=ApplicationEventType.SAFETY_VERIFIED,
        previous_status=None,
        new_status=None,
        reason="Safety pre-apply pass",
        triggering_component="SafetyEngine",
        timestamp=datetime.now(timezone.utc),
    )
    await event_repo.append_event(event1)
    await event_repo.append_event(event2)

    response = client.get(f"/api/v1/applications/{app_id}/events")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["event_type"] == "STATE_TRANSITION"
    assert data[0]["previous_status"] == "DISCOVERED"
    assert data[0]["new_status"] == "MATCHED"
    assert data[1]["event_type"] == "SAFETY_VERIFIED"


@pytest.mark.asyncio
async def test_api_approve_application_success(client: TestClient, clean_repos):
    """Verify approving application transitions AWAITING_APPROVAL -> FILLING."""
    app_repo, _ = clean_repos
    app_id = uuid.uuid4()
    user_id = uuid.uuid4()
    app = Application(
        id=app_id,
        user_id=user_id,
        job_id=uuid.uuid4(),
        platform="greenhouse",
        external_id="ext-202",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.AWAITING_APPROVAL,
        approval_status=ApprovalStatus.PENDING,
        idempotency_key="token-test-202",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await app_repo.create(app)

    response = client.post(
        f"/api/v1/applications/{app_id}/approve",
        json={"user_id": str(user_id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FILLING"
    assert data["approval_status"] == "APPROVED"
    assert data["approved_at"] is not None


@pytest.mark.asyncio
async def test_api_approve_application_invalid_state(client: TestClient, clean_repos):
    """Verify approving application not in AWAITING_APPROVAL returns 409 Conflict."""
    app_repo, _ = clean_repos
    app_id = uuid.uuid4()
    user_id = uuid.uuid4()
    app = Application(
        id=app_id,
        user_id=user_id,
        job_id=uuid.uuid4(),
        platform="greenhouse",
        external_id="ext-203",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.MATCHED,
        idempotency_key="token-test-203",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await app_repo.create(app)

    response = client.post(
        f"/api/v1/applications/{app_id}/approve",
        json={"user_id": str(user_id)},
    )
    assert response.status_code == 409
    assert "Invalid state transition" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_reject_application_success(client: TestClient, clean_repos):
    """Verify user rejection transitions application to REJECTED."""
    app_repo, _ = clean_repos
    app_id = uuid.uuid4()
    user_id = uuid.uuid4()
    app = Application(
        id=app_id,
        user_id=user_id,
        job_id=uuid.uuid4(),
        platform="greenhouse",
        external_id="ext-204",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="token-test-204",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await app_repo.create(app)

    response = client.post(
        f"/api/v1/applications/{app_id}/reject",
        json={"user_id": str(user_id), "reason": "Not interested in company"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "REJECTED"
    assert data["approval_status"] == "REJECTED"


@pytest.mark.asyncio
async def test_api_execute_dry_run_requires_approval(client: TestClient, clean_repos):
    """Verify dry-run execution is rejected if application has not been approved."""
    app_repo, _ = clean_repos
    app_id = uuid.uuid4()
    user_id = uuid.uuid4()
    app = Application(
        id=app_id,
        user_id=user_id,
        job_id=uuid.uuid4(),
        platform="greenhouse",
        external_id="ext-205",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.AWAITING_APPROVAL,
        approval_status=ApprovalStatus.PENDING,
        idempotency_key="token-test-205",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await app_repo.create(app)

    response = client.post(
        f"/api/v1/applications/{app_id}/execute-dry-run?user_id={user_id}",
        json={"company": "Example Software"},
    )
    assert response.status_code == 403
    assert "requires explicit user approval" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_execute_dry_run_success(client: TestClient, clean_repos):
    """Verify dry-run execution succeeds for approved application in FILLING status."""
    app_repo, _ = clean_repos
    app_id = uuid.uuid4()
    user_id = uuid.uuid4()
    app = Application(
        id=app_id,
        user_id=user_id,
        job_id=uuid.uuid4(),
        platform="greenhouse",
        external_id="ext-206",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.FILLING,
        approval_status=ApprovalStatus.APPROVED,
        approved_at=datetime.now(timezone.utc),
        idempotency_key="token-test-206",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await app_repo.create(app)

    response = client.post(
        f"/api/v1/applications/{app_id}/execute-dry-run?user_id={user_id}",
        json={"company": "Example Software"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "DRY_RUN_DONE"
    assert data["evidence_ref"] is not None


def test_api_auth_token_enforcement(clean_repos, orchestrator, mock_safety_engine):
    """Verify 401 is returned when worker_token is configured and not provided."""
    app_repo, event_repo = clean_repos
    token_settings = Settings(
        worker_token="secure-test-token-777",
        api_host="127.0.0.1",
        allow_tokenless_dev=False,
    )
    app = create_app(token_settings)
    app.dependency_overrides[get_application_repository] = lambda: app_repo
    app.dependency_overrides[get_application_event_repository] = lambda: event_repo
    app.dependency_overrides[get_application_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_safety_engine] = lambda: mock_safety_engine

    client = TestClient(app)

    # Missing token -> 401
    resp_unauth = client.get(f"/api/v1/applications/{uuid.uuid4()}")
    assert resp_unauth.status_code == 401

    # Valid token via X-Worker-Token -> 404 (authorized, resource not found)
    resp_auth = client.get(
        f"/api/v1/applications/{uuid.uuid4()}",
        headers={"X-Worker-Token": "secure-test-token-777"},
    )
    assert resp_auth.status_code == 404
