"""Tests for Telegram Notification and Owner Command Service (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Appendix B)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
from uuid import uuid4
import pytest

from worker.application.models import Application, ApplicationStatus
from worker.application.orchestrator import ApplicationOrchestrator
from worker.application.repository import (
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)
from worker.core.kill_switch import InMemoryKillSwitch
from worker.ops.approval import ApprovalManager
from worker.ops.provider_health import ProviderHealthManager
from worker.ops.telegram import (
    MockTelegramNotifier,
    TelegramNotificationService,
    TelegramSecurityError,
)


@pytest.fixture
def telegram_env():
    app_repo = InMemoryApplicationRepository()
    event_repo = InMemoryApplicationEventRepository()
    orchestrator = ApplicationOrchestrator(
        application_repo=app_repo,
        event_repo=event_repo,
        matching_service=None,
        safety_engine=None,
        runner=None,
    )
    approval_mgr = ApprovalManager(orchestrator, app_repo, event_repo)
    kill_switch = InMemoryKillSwitch(initial_enabled=True)
    health_mgr = ProviderHealthManager()
    mock_notifier = MockTelegramNotifier()

    service = TelegramNotificationService(
        bot_token=None,  # mock
        allowed_chat_ids=[123456],
        notifier=mock_notifier,
        approval_manager=approval_mgr,
        kill_switch=kill_switch,
        provider_health_mgr=health_mgr,
    )
    return {
        "service": service,
        "notifier": mock_notifier,
        "approval_mgr": approval_mgr,
        "kill_switch": kill_switch,
        "health_mgr": health_mgr,
        "app_repo": app_repo,
    }


@pytest.mark.asyncio
async def test_outbound_notifications_dispatch_cleanly(telegram_env):
    svc = telegram_env["service"]
    notifier = telegram_env["notifier"]

    app_id = uuid4()
    await svc.notify_approval_requested(app_id, "Stripe", "Senior Engineer", 89.2)
    assert len(notifier.sent_messages) == 1
    assert "Senior Engineer" in notifier.sent_messages[0]["text"]
    assert str(app_id) in notifier.sent_messages[0]["text"]

    await svc.notify_needs_user_input(app_id, ["experience_years", "salary_expectation"])
    assert len(notifier.sent_messages) == 2

    await svc.notify_manual_intervention(app_id, "Cloudflare Turnstile challenge detected")
    assert len(notifier.sent_messages) == 3

    await svc.notify_provider_auto_pause("lever", "3 consecutive selector errors", 3)
    assert len(notifier.sent_messages) == 4

    await svc.notify_kill_switch_activated("Manual trip", "admin")
    assert len(notifier.sent_messages) == 5

    await svc.notify_llm_budget_exhausted(2.10, 2.00)
    assert len(notifier.sent_messages) == 6

    await svc.notify_heartbeat_failure("worker-1", datetime.now(timezone.utc))
    assert len(notifier.sent_messages) == 7


@pytest.mark.asyncio
async def test_telegram_unauthorized_chat_rejected(telegram_env):
    svc = telegram_env["service"]
    user_id = uuid4()

    with pytest.raises(TelegramSecurityError, match="Unauthorized chat ID"):
        await svc.handle_command(chat_id=999999, command_text="/status", user_id=user_id)


@pytest.mark.asyncio
async def test_telegram_owner_commands_status_kill_pause_resume(telegram_env):
    svc = telegram_env["service"]
    ks = telegram_env["kill_switch"]
    health = telegram_env["health_mgr"]
    user_id = uuid4()

    # /status
    res_status = await svc.handle_command(123456, "/status", user_id)
    assert "Job Agent Status" in res_status

    # /kill
    res_kill = await svc.handle_command(123456, "/kill Emergency test", user_id)
    assert "ACTIVATED" in res_kill
    assert not ks.is_automation_enabled()

    # /pause
    res_pause = await svc.handle_command(123456, "/pause greenhouse", user_id)
    assert "PAUSED" in res_pause
    assert health.is_provider_available("greenhouse") is False

    # /resume
    res_resume = await svc.handle_command(123456, "/resume greenhouse", user_id)
    assert "RESUMED" in res_resume
    assert health.is_provider_available("greenhouse") is True


@pytest.mark.asyncio
async def test_telegram_owner_approve_and_reject_commands(telegram_env):
    svc = telegram_env["service"]
    app_repo = telegram_env["app_repo"]
    user_id = uuid4()

    app = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-tg-app",
        profile_version="v1.0",
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="key-tg-app",
    )
    await app_repo.create(app)

    # Approve
    res_app = await svc.handle_command(123456, f"/approve {app.id}", user_id)
    assert "APPROVED" in res_app

    updated = await app_repo.get_by_id(app.id)
    assert updated.status == ApplicationStatus.FILLING

    # Reject another
    app2 = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="lever",
        external_id="ext-tg-app2",
        profile_version="v1.0",
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="key-tg-app2",
    )
    await app_repo.create(app2)

    res_rej = await svc.handle_command(123456, f"/reject {app2.id} Salary too low", user_id)
    assert "REJECTED" in res_rej
    updated2 = await app_repo.get_by_id(app2.id)
    assert updated2.status == ApplicationStatus.REJECTED
