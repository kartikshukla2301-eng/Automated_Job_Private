"""Tests for Human-in-the-loop Approval & User-Input Manager (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 13)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone, timedelta
from uuid import uuid4
import pytest

from worker.application.exceptions import (
    ApplicationNotFoundError,
    TerminalStateError,
)
from worker.application.models import (
    Application,
    ApplicationStatus,
    ApprovalStatus,
    AutonomyLevel,
)
from worker.application.orchestrator import ApplicationOrchestrator
from worker.application.repository import (
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)
from worker.ops.approval import (
    ApprovalAuthorizationError,
    ApprovalExpiredError,
    ApprovalManager,
    ApprovalStateError,
)


@pytest.fixture
def repos():
    app_repo = InMemoryApplicationRepository()
    event_repo = InMemoryApplicationEventRepository()
    return app_repo, event_repo


@pytest.fixture
def orchestrator(repos):
    app_repo, event_repo = repos
    # Orchestrator with mock services
    return ApplicationOrchestrator(
        application_repo=app_repo,
        event_repo=event_repo,
        matching_service=None,  # Not invoked in approval tests
        safety_engine=None,
        runner=None,
    )


@pytest.fixture
def approval_mgr(repos, orchestrator):
    app_repo, event_repo = repos
    return ApprovalManager(
        orchestrator=orchestrator,
        application_repo=app_repo,
        event_repo=event_repo,
        default_ttl_hours=24.0,
    )


@pytest.mark.asyncio
async def test_approval_queue_filtering_and_ownership(repos, approval_mgr):
    app_repo, _ = repos
    user_a = uuid4()
    user_b = uuid4()

    app_a = Application(
        id=uuid4(),
        user_id=user_a,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-1",
        profile_version="v1.0",
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="key-1",
    )
    app_b = Application(
        id=uuid4(),
        user_id=user_b,
        job_id=uuid4(),
        platform="lever",
        external_id="ext-2",
        profile_version="v1.0",
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="key-2",
    )
    await app_repo.create(app_a)
    await app_repo.create(app_b)

    queue_a = await approval_mgr.get_approval_queue(user_a)
    assert len(queue_a) == 1
    assert queue_a[0].id == app_a.id

    queue_b = await approval_mgr.get_approval_queue(user_b)
    assert len(queue_b) == 1
    assert queue_b[0].id == app_b.id


@pytest.mark.asyncio
async def test_approve_application_success(repos, approval_mgr):
    app_repo, event_repo = repos
    user_id = uuid4()
    app = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-app-ok",
        profile_version="v1.0",
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="key-app-ok",
    )
    await app_repo.create(app)

    approved = await approval_mgr.approve_application(
        application_id=app.id,
        user_id=user_id,
        actor="test_user",
    )
    assert approved.status == ApplicationStatus.FILLING
    assert approved.approval_status == ApprovalStatus.APPROVED
    assert approved.approved_at is not None

    events = await event_repo.list_by_application_id(app.id)
    assert any(e.event_type == "APPROVAL_GRANTED" for e in events)


@pytest.mark.asyncio
async def test_approve_unauthorized_user_raises_error(repos, approval_mgr):
    app_repo, _ = repos
    owner_id = uuid4()
    attacker_id = uuid4()
    app = Application(
        id=uuid4(),
        user_id=owner_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-unauth",
        profile_version="v1.0",
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="key-unauth",
    )
    await app_repo.create(app)

    with pytest.raises(ApprovalAuthorizationError, match="Unauthorized"):
        await approval_mgr.approve_application(
            application_id=app.id,
            user_id=attacker_id,
        )


@pytest.mark.asyncio
async def test_approve_expired_application_raises_and_transitions(repos, approval_mgr):
    app_repo, _ = repos
    user_id = uuid4()
    # 25 hours old (TTL is 24.0h)
    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    app = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-exp",
        profile_version="v1.0",
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="key-exp",
        created_at=old_time,
        updated_at=old_time,
    )
    await app_repo.create(app)

    with pytest.raises(ApprovalExpiredError, match="Approval window.*expired"):
        await approval_mgr.approve_application(application_id=app.id, user_id=user_id)

    updated = await app_repo.get_by_id(app.id)
    assert updated.status == ApplicationStatus.EXPIRED
    assert updated.approval_status == ApprovalStatus.EXPIRED


@pytest.mark.asyncio
async def test_approve_blocked_or_terminal_rejected(repos, approval_mgr):
    app_repo, _ = repos
    user_id = uuid4()
    blocked_app = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-blk",
        profile_version="v1.0",
        status=ApplicationStatus.BLOCKED,
        idempotency_key="key-blk",
    )
    await app_repo.create(blocked_app)

    with pytest.raises(ApprovalStateError, match="blocked"):
        await approval_mgr.approve_application(blocked_app.id, user_id)

    rejected_app = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-term",
        profile_version="v1.0",
        status=ApplicationStatus.REJECTED,
        idempotency_key="key-term",
    )
    await app_repo.create(rejected_app)

    with pytest.raises(TerminalStateError, match="terminal state"):
        await approval_mgr.approve_application(rejected_app.id, user_id)


@pytest.mark.asyncio
async def test_resolve_user_input_flow(repos, approval_mgr):
    app_repo, event_repo = repos
    user_id = uuid4()
    app = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-input",
        profile_version="v1.0",
        status=ApplicationStatus.NEEDS_USER_INPUT,
        idempotency_key="key-input",
    )
    await app_repo.create(app)

    updated = await approval_mgr.resolve_user_input(
        application_id=app.id,
        user_id=user_id,
        provided_answers={"years_of_experience": "5", "notice_period": "30 days"},
    )
    assert updated.status == ApplicationStatus.FILLING

    events = await event_repo.list_by_application_id(app.id)
    assert any(e.new_status == ApplicationStatus.FILLING for e in events)


@pytest.mark.asyncio
async def test_get_safe_application_detail(repos, approval_mgr):
    app_repo, _ = repos
    user_id = uuid4()
    app = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="lever",
        external_id="ext-safe",
        profile_version="v1.0",
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="key-safe",
        score=88.5,
    )
    await app_repo.create(app)

    detail = await approval_mgr.get_safe_application_detail(app.id, user_id)
    assert detail["id"] == str(app.id)
    assert detail["platform"] == "lever"
    assert detail["score"] == 88.5
    assert "password" not in detail
    assert "token" not in detail
