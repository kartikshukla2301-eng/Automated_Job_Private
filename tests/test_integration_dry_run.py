"""Integration tests for Phase 0.8 Walking Skeleton.

Verifies end-to-end integration between FastAPI, candidate ProfileSource,
SafetyEngine, JobApplicationRunner, and GreenhouseProvider.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from services.api.config import CapsConfig, Settings
from services.api.dependencies import get_safety_engine
from services.api.main import create_app
from worker.core.caps import CapsEnforcer, InMemoryApplicationLedger
from worker.core.exceptions import (
    GlobalDailyCapExceededError,
    InvalidSafetyStateError,
    KillSwitchActiveError,
)
from worker.core.kill_switch import FileKillSwitch, InMemoryKillSwitch
from worker.core.safety import SafetyEngine
from worker.core.workflow import WalkingSkeletonWorkflow
from worker.profile.exceptions import ProfileNotFoundError
from worker.profile.localfile import LocalFileProfileSource


@pytest.fixture
def test_profile_source() -> LocalFileProfileSource:
    return LocalFileProfileSource("fixtures/profile.yaml")


@pytest.fixture
def open_safety_engine() -> SafetyEngine:
    ks = InMemoryKillSwitch(initial_enabled=True)
    caps_cfg = CapsConfig(global_per_day=20, per_company_per_day=5, per_company_per_30d=5)
    ledger = InMemoryApplicationLedger()
    enforcer = CapsEnforcer(caps_cfg, ledger)
    return SafetyEngine(kill_switch=ks, caps_enforcer=enforcer, real_submit_gate_enabled=False)


@pytest.mark.asyncio
async def test_walking_skeleton_workflow_end_to_end(
    test_profile_source: LocalFileProfileSource,
    open_safety_engine: SafetyEngine,
    tmp_path: Path,
):
    """Verify safe end-to-end dry run execution against approved Greenhouse fixture."""
    evidence_dir = tmp_path / "evidence"
    workflow = WalkingSkeletonWorkflow(
        safety_engine=open_safety_engine,
        profile_source=test_profile_source,
        evidence_dir=evidence_dir,
    )

    result = await workflow.run_greenhouse_dry_run(company="Example Software")

    assert result.status == "DRY_RUN_COMPLETED"
    assert result.company == "Example Software"
    assert result.provider == "greenhouse"
    assert result.profile_version == "template-v1.0.0"

    # Truthfully resolved fields
    assert result.fields_filled.get("First Name *") == "Candidate"
    assert result.fields_filled.get("Last Name *") == "Name Placeholder"
    assert result.fields_filled.get("Email *") == "candidate.placeholder@example.com"
    assert result.fields_filled.get("Phone *") == "+1-555-0100"
    assert result.fields_filled.get("LinkedIn Profile") == "https://linkedin.com/in/example-candidate"
    assert result.fields_filled.get("Website / Portfolio") == "https://example-candidate.dev"

    # Unresolved fields requiring user review or Answer Bank
    assert "What is your current notice period in days? *" in result.unresolved_fields
    assert "Why are you interested in joining Example Software?" in result.unresolved_fields

    # Sensitive fields strictly omitted
    for sensitive_name in ["resume", "password", "account_password", "otp_verification", "otp_code"]:
        assert sensitive_name not in result.fields_filled

    # Evidence screenshot captured
    assert result.screenshot_path is not None
    assert Path(result.screenshot_path).exists()
    assert result.safety_decision is not None
    assert result.safety_decision.allowed is True


def test_fastapi_dry_run_endpoint_success(open_safety_engine: SafetyEngine):
    """Verify FastAPI endpoint triggers dry-run workflow and returns structured response."""
    dev_settings = Settings(allow_tokenless_dev=True, api_host="127.0.0.1")
    app = create_app(dev_settings)
    app.dependency_overrides[get_safety_engine] = lambda: open_safety_engine

    client = TestClient(app)
    response = client.post(
        "/api/v1/dry-run/greenhouse",
        json={"company": "Example Software"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "DRY_RUN_COMPLETED"
    assert data["company"] == "Example Software"
    assert data["provider"] == "greenhouse"
    assert data["fields_filled"]["First Name *"] == "Candidate"
    assert data["fields_filled"]["Email *"] == "candidate.placeholder@example.com"
    assert len(data["unresolved_fields"]) >= 2
    assert data["safety_allowed"] is True
    assert data["screenshot_path"] is not None

    # Verify no absolute host paths or usernames leaked
    assert not data["job_url"].startswith("C:")
    assert not data["screenshot_path"].startswith("C:")
    assert "Users" not in data["screenshot_path"]
    assert "Kartik Shukla" not in data["job_url"]
    assert "Kartik Shukla" not in data["screenshot_path"]


def test_fastapi_dry_run_rejects_extra_fields(open_safety_engine: SafetyEngine):
    """Verify API rejects attempts to supply arbitrary URLs or extra parameters."""
    dev_settings = Settings(allow_tokenless_dev=True, api_host="127.0.0.1")
    app = create_app(dev_settings)
    app.dependency_overrides[get_safety_engine] = lambda: open_safety_engine
    client = TestClient(app)

    # Attempting to supply an external URL or custom path
    response = client.post(
        "/api/v1/dry-run/greenhouse",
        json={
            "company": "Example Software",
            "url": "https://external-job-board.example.com",
        },
    )

    # extra='forbid' rejects extra fields with HTTP 422
    assert response.status_code == 422
    assert "extra_forbidden" in str(response.json())


def test_fastapi_dry_run_blocks_when_kill_switch_active(open_safety_engine: SafetyEngine):
    """Verify API returns 423 Locked when kill switch is tripped, before any browser launch."""
    open_safety_engine.kill_switch.trip(reason="Emergency admin stop")

    dev_settings = Settings(allow_tokenless_dev=True, api_host="127.0.0.1")
    app = create_app(dev_settings)
    app.dependency_overrides[get_safety_engine] = lambda: open_safety_engine

    client = TestClient(app)
    response = client.post(
        "/api/v1/dry-run/greenhouse",
        json={"company": "Example Software"},
    )

    assert response.status_code == 423
    data = response.json()
    assert data["error"] == "kill_switch_active"
    assert data["blocked_by"] == "kill_switch"
    assert "Emergency admin stop" in data["detail"]


def test_missing_kill_switch_fails_closed_in_api(tmp_path: Path):
    """Verify missing kill switch file fails closed with HTTP 500 invalid safety state."""
    missing_file = tmp_path / "missing_kill_switch.json"
    ks = FileKillSwitch(missing_file)
    caps_cfg = CapsConfig(global_per_day=10)
    enforcer = CapsEnforcer(caps_cfg, InMemoryApplicationLedger())
    engine = SafetyEngine(kill_switch=ks, caps_enforcer=enforcer)

    dev_settings = Settings(allow_tokenless_dev=True, api_host="127.0.0.1")
    app = create_app(dev_settings)
    app.dependency_overrides[get_safety_engine] = lambda: engine

    client = TestClient(app)
    response = client.post(
        "/api/v1/dry-run/greenhouse",
        json={"company": "Example Software"},
    )

    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "invalid_safety_state"
    assert data["blocked_by"] == "invalid_safety_state"


def test_caps_exceeded_blocks_execution_in_api(open_safety_engine: SafetyEngine):
    """Verify API returns 429 Too Many Requests when daily cap is exhausted."""
    # Configure 0 daily cap
    zero_caps = CapsConfig(global_per_day=0)
    open_safety_engine.caps_enforcer.config = zero_caps

    dev_settings = Settings(allow_tokenless_dev=True, api_host="127.0.0.1")
    app = create_app(dev_settings)
    app.dependency_overrides[get_safety_engine] = lambda: open_safety_engine

    client = TestClient(app)
    response = client.post(
        "/api/v1/dry-run/greenhouse",
        json={"company": "Example Software"},
    )

    assert response.status_code == 429
    data = response.json()
    assert data["error"] == "cap_exceeded"
    assert data["blocked_by"] == "application_caps"


def test_worker_token_authentication(open_safety_engine: SafetyEngine):
    """Verify worker token authentication protects endpoint when configured."""
    custom_settings = Settings(worker_token="secure_worker_token_xyz")
    app = create_app(custom_settings)
    app.dependency_overrides[get_safety_engine] = lambda: open_safety_engine
    client = TestClient(app)

    # 1. No token -> 401
    resp_no_token = client.post("/api/v1/dry-run/greenhouse", json={"company": "Example Software"})
    assert resp_no_token.status_code == 401

    # 2. Invalid token -> 401
    resp_bad_token = client.post(
        "/api/v1/dry-run/greenhouse",
        json={"company": "Example Software"},
        headers={"X-Worker-Token": "wrong_token"},
    )
    assert resp_bad_token.status_code == 401

    # 3. Valid X-Worker-Token -> 200
    resp_header = client.post(
        "/api/v1/dry-run/greenhouse",
        json={"company": "Example Software"},
        headers={"X-Worker-Token": "secure_worker_token_xyz"},
    )
    assert resp_header.status_code == 200

    # 4. Valid Authorization Bearer -> 200
    resp_bearer = client.post(
        "/api/v1/dry-run/greenhouse",
        json={"company": "Example Software"},
        headers={"Authorization": "Bearer secure_worker_token_xyz"},
    )
    assert resp_bearer.status_code == 200


def test_worker_token_missing_rejected_when_auth_required(open_safety_engine: SafetyEngine):
    """Verify request without token is rejected when allow_tokenless_dev is False."""
    strict_dev = Settings(app_env="development", allow_tokenless_dev=False, worker_token=None)
    app = create_app(strict_dev)
    app.dependency_overrides[get_safety_engine] = lambda: open_safety_engine
    client = TestClient(app)

    response = client.post("/api/v1/dry-run/greenhouse", json={"company": "Example Software"})
    assert response.status_code == 401
    assert "Worker authentication required" in response.json()["detail"]


def test_worker_token_missing_fails_closed_in_production_and_staging(open_safety_engine: SafetyEngine):
    """Verify production and staging fail closed with HTTP 500 when worker_token is not configured."""
    prod_settings = Settings(app_env="production", worker_token=None)
    prod_app = create_app(prod_settings)
    prod_app.dependency_overrides[get_safety_engine] = lambda: open_safety_engine
    client = TestClient(prod_app)

    prod_resp = client.post("/api/v1/dry-run/greenhouse", json={"company": "Example Software"})
    assert prod_resp.status_code == 500
    assert "Worker authentication must be configured in production and staging" in prod_resp.json()["detail"]

    staging_settings = Settings(app_env="staging", worker_token=None)
    staging_app = create_app(staging_settings)
    staging_app.dependency_overrides[get_safety_engine] = lambda: open_safety_engine
    client_staging = TestClient(staging_app)

    staging_resp = client_staging.post("/api/v1/dry-run/greenhouse", json={"company": "Example Software"})
    assert staging_resp.status_code == 500
    assert "Worker authentication must be configured in production and staging" in staging_resp.json()["detail"]


def test_tokenless_dev_rejected_on_non_local_host(open_safety_engine: SafetyEngine):
    """Verify tokenless execution is forbidden when host is non-local even in development."""
    external_dev = Settings(app_env="development", allow_tokenless_dev=True, api_host="0.0.0.0")
    app = create_app(external_dev)
    app.dependency_overrides[get_safety_engine] = lambda: open_safety_engine
    client = TestClient(app)

    resp = client.post("/api/v1/dry-run/greenhouse", json={"company": "Example Software"})
    assert resp.status_code == 403
    assert "non-local network interfaces" in resp.json()["detail"]


def test_settings_injected_via_app_state():
    """Verify multiple FastAPI apps maintain isolated settings on app.state without override leakage."""
    app_a = create_app(Settings(app_name="App Alpha", app_version="1.0.0"))
    app_b = create_app(Settings(app_name="App Beta", app_version="2.0.0"))

    client_a = TestClient(app_a)
    client_b = TestClient(app_b)

    resp_a = client_a.get("/health")
    resp_b = client_b.get("/health")

    assert resp_a.status_code == 200
    assert resp_a.json()["version"] == "1.0.0"

    assert resp_b.status_code == 200
    assert resp_b.json()["version"] == "2.0.0"


def test_file_not_found_error_does_not_expose_filesystem_paths(
    open_safety_engine: SafetyEngine,
    test_profile_source: LocalFileProfileSource,
):
    """Verify FileNotFoundError in route returns generic error without raw host filesystem paths."""
    from services.api.dependencies import get_walking_skeleton_workflow

    workflow = WalkingSkeletonWorkflow(
        safety_engine=open_safety_engine,
        profile_source=test_profile_source,
        fixture_path=Path("fixtures/forms/does_not_exist_fixture.html"),
    )
    dev_settings = Settings(allow_tokenless_dev=True, api_host="127.0.0.1")
    app = create_app(dev_settings)
    app.dependency_overrides[get_walking_skeleton_workflow] = lambda: workflow

    client = TestClient(app)
    response = client.post("/api/v1/dry-run/greenhouse", json={"company": "Example Software"})

    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "resource_not_found"
    assert data["detail"] == "Requested job fixture or required local resource was not found."
    # Ensure no raw Windows paths or drive roots are present in the response
    assert "C:" not in data["detail"]
    assert "\\" not in data["detail"]
    assert "Kartik Shukla" not in data["detail"]


@pytest.mark.asyncio
async def test_workflow_fails_when_profile_file_missing(open_safety_engine: SafetyEngine):
    """Verify workflow fails gracefully when candidate profile file cannot be found."""
    missing_source = LocalFileProfileSource("fixtures/non_existent_profile.yaml")
    workflow = WalkingSkeletonWorkflow(
        safety_engine=open_safety_engine,
        profile_source=missing_source,
    )

    with pytest.raises(ProfileNotFoundError):
        await workflow.run_greenhouse_dry_run(company="Example Software")


@pytest.mark.asyncio
async def test_workflow_fails_when_fixture_missing(
    open_safety_engine: SafetyEngine,
    test_profile_source: LocalFileProfileSource,
):
    """Verify workflow rejects non-existent fixture path."""
    workflow = WalkingSkeletonWorkflow(
        safety_engine=open_safety_engine,
        profile_source=test_profile_source,
        fixture_path=Path("fixtures/forms/does_not_exist.html"),
    )

    with pytest.raises(FileNotFoundError):
        await workflow.run_greenhouse_dry_run(company="Example Software")


@pytest.mark.asyncio
async def test_no_submission_action_executed(
    test_profile_source: LocalFileProfileSource,
    open_safety_engine: SafetyEngine,
    tmp_path: Path,
):
    """Verify that submit button is never clicked and form submission never occurs."""
    assert open_safety_engine.real_submit_gate_enabled is False

    workflow = WalkingSkeletonWorkflow(
        safety_engine=open_safety_engine,
        profile_source=test_profile_source,
        evidence_dir=tmp_path / "evidence",
    )

    result = await workflow.run_greenhouse_dry_run(company="Example Software")

    # Result status must be DRY_RUN_COMPLETED, never SUBMITTED or APPLIED
    assert result.status == "DRY_RUN_COMPLETED"
    assert result.status != "APPLIED"
    assert result.status != "SUBMITTING"
