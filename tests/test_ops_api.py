"""Tests for Operations API endpoints (/api/v1/ops/*).

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
    get_approval_manager,
    get_canary_runner,
    get_heartbeat_manager,
    get_metrics_aggregator,
    get_provider_health_manager,
    get_readiness_evaluator,
    get_safety_engine,
    get_telegram_service,
)
from services.api.main import create_app
from worker.application.models import Application, ApplicationStatus, AutonomyLevel
from worker.application.orchestrator import ApplicationOrchestrator
from worker.application.repository import (
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)
from worker.core.caps import CapsEnforcer, InMemoryApplicationLedger
from worker.core.kill_switch import InMemoryKillSwitch
from worker.core.safety import SafetyEngine
from worker.ops.approval import ApprovalManager
from worker.ops.canary import ProviderCanaryRunner
from worker.ops.heartbeat import HeartbeatManager
from worker.ops.metrics import MetricsAggregator
from worker.ops.provider_health import ProviderHealthManager
from worker.ops.readiness import RealSubmitReadinessEvaluator
from worker.ops.telegram import MockTelegramNotifier, TelegramNotificationService


@pytest.fixture
def ops_test_env():
    app_repo = InMemoryApplicationRepository()
    event_repo = InMemoryApplicationEventRepository()
    ks = InMemoryKillSwitch(initial_enabled=True)
    ledger = InMemoryApplicationLedger()
    enforcer = CapsEnforcer(CapsConfig(global_per_day=20, per_company_per_day=5), ledger)
    safety_engine = SafetyEngine(kill_switch=ks, caps_enforcer=enforcer, real_submit_gate_enabled=False)

    orchestrator = ApplicationOrchestrator(
        application_repo=app_repo,
        event_repo=event_repo,
        matching_service=None,
        safety_engine=safety_engine,
        runner=None,
    )
    approval_mgr = ApprovalManager(orchestrator, app_repo, event_repo)
    health_mgr = ProviderHealthManager()
    heartbeat_mgr = HeartbeatManager()
    canary_runner = ProviderCanaryRunner(health_mgr=health_mgr)
    metrics_agg = MetricsAggregator(app_repo, event_repo, health_mgr=health_mgr)
    telegram_svc = TelegramNotificationService(
        bot_token=None,
        allowed_chat_ids=[12345],
        notifier=MockTelegramNotifier(),
        approval_manager=approval_mgr,
        kill_switch=ks,
        provider_health_mgr=health_mgr,
    )
    readiness_evaluator = RealSubmitReadinessEvaluator()

    dev_settings = Settings(allow_tokenless_dev=True, api_host="127.0.0.1")
    app = create_app(dev_settings)

    app.dependency_overrides[get_application_repository] = lambda: app_repo
    app.dependency_overrides[get_application_event_repository] = lambda: event_repo
    app.dependency_overrides[get_application_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_safety_engine] = lambda: safety_engine
    app.dependency_overrides[get_approval_manager] = lambda: approval_mgr
    app.dependency_overrides[get_provider_health_manager] = lambda: health_mgr
    app.dependency_overrides[get_heartbeat_manager] = lambda: heartbeat_mgr
    app.dependency_overrides[get_canary_runner] = lambda: canary_runner
    app.dependency_overrides[get_metrics_aggregator] = lambda: metrics_agg
    app.dependency_overrides[get_telegram_service] = lambda: telegram_svc
    app.dependency_overrides[get_readiness_evaluator] = lambda: readiness_evaluator

    client = TestClient(app)
    return {
        "client": client,
        "app_repo": app_repo,
        "event_repo": event_repo,
        "health_mgr": health_mgr,
        "heartbeat_mgr": heartbeat_mgr,
    }


def test_api_get_approval_queue(ops_test_env):
    client = ops_test_env["client"]
    app_repo = ops_test_env["app_repo"]
    user_id = uuid4()

    app = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-q1",
        profile_version="v1.0",
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="key-q1",
    )
    import asyncio
    asyncio.run(app_repo.create(app))

    resp = client.get(f"/api/v1/ops/approvals?user_id={user_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == str(app.id)


def test_api_resolve_user_input(ops_test_env):
    client = ops_test_env["client"]
    app_repo = ops_test_env["app_repo"]
    user_id = uuid4()

    app = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="lever",
        external_id="ext-inp1",
        profile_version="v1.0",
        status=ApplicationStatus.NEEDS_USER_INPUT,
        idempotency_key="key-inp1",
    )
    import asyncio
    asyncio.run(app_repo.create(app))

    resp = client.post(
        f"/api/v1/ops/approvals/{app.id}/resolve-input",
        json={
            "user_id": str(user_id),
            "answers": {"salary_expectation": "$120,000", "authorization": "yes"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "FILLING"


def test_api_provider_health_pause_resume(ops_test_env):
    client = ops_test_env["client"]

    # Pause
    resp_pause = client.post("/api/v1/ops/provider-health/greenhouse/pause")
    assert resp_pause.status_code == 200
    assert resp_pause.json()["status"] == "PAUSED"

    # List
    resp_list = client.get("/api/v1/ops/provider-health")
    assert resp_list.status_code == 200
    items = resp_list.json()
    assert any(i["provider_name"] == "greenhouse" and i["status"] == "PAUSED" for i in items)

    # Resume
    resp_resume = client.post("/api/v1/ops/provider-health/greenhouse/resume")
    assert resp_resume.status_code == 200
    assert resp_resume.json()["status"] == "HEALTHY"


def test_api_heartbeat_and_pulse(ops_test_env):
    client = ops_test_env["client"]

    resp = client.get("/api/v1/ops/heartbeat")
    assert resp.status_code == 200
    assert resp.json()["status"] == "HEALTHY"

    resp_pulse = client.post("/api/v1/ops/heartbeat/pulse")
    assert resp_pulse.status_code == 200
    assert resp_pulse.json()["status"] == "HEALTHY"


def test_api_run_canary(ops_test_env):
    client = ops_test_env["client"]

    resp = client.post("/api/v1/ops/canaries/greenhouse/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_available"] is True
    assert data["safe_to_operate"] is True


def test_api_get_metrics(ops_test_env):
    client = ops_test_env["client"]
    user_id = uuid4()

    resp = client.get(f"/api/v1/ops/metrics?user_id={user_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(user_id)
    assert "applications_total" in data


def test_api_get_readiness_report(ops_test_env):
    client = ops_test_env["client"]

    resp = client.get("/api/v1/ops/readiness")
    assert resp.status_code == 200
    data = resp.json()
    assert data["real_submit_gate_enabled"] is False  # MUST BE FALSE
    assert len(data["criteria"]) == 8


def test_api_telegram_webhook(ops_test_env):
    client = ops_test_env["client"]
    user_id = uuid4()

    # Valid command from authorized chat
    resp = client.post(
        "/api/v1/ops/telegram/webhook",
        json={"chat_id": 12345, "command_text": "/status", "user_id": str(user_id)},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Unauthorized chat ID
    resp_unauth = client.post(
        "/api/v1/ops/telegram/webhook",
        json={"chat_id": 99999, "command_text": "/status", "user_id": str(user_id)},
    )
    assert resp_unauth.status_code == 403
