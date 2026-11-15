"""Unit tests for Application and ApplicationEvent repositories.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 13, 14)
- migrations/001_initial_schema.sql
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from worker.application.exceptions import (
    ApplicationNotFoundError,
    DuplicateApplicationError,
    IdempotencyConflictError,
)
from worker.application.models import (
    Application,
    ApplicationEvent,
    ApplicationStatus,
    AutonomyLevel,
)
from worker.application.repository import (
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)


@pytest.fixture
def repo() -> InMemoryApplicationRepository:
    return InMemoryApplicationRepository()


@pytest.fixture
def event_repo() -> InMemoryApplicationEventRepository:
    return InMemoryApplicationEventRepository()


def make_app(
    user_id=None,
    job_id=None,
    external_id="ext-1",
    idempotency_key=None,
    status=ApplicationStatus.DISCOVERED,
) -> Application:
    now = datetime.now(timezone.utc)
    u_id = user_id or uuid4()
    j_id = job_id or uuid4()
    idmp = idempotency_key or f"idmp_{u_id}_{j_id}"
    return Application(
        id=uuid4(),
        user_id=u_id,
        job_id=j_id,
        platform="greenhouse",
        external_id=external_id,
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=status,
        idempotency_key=idmp,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_repo_create_and_get(repo):
    app = make_app()
    created = await repo.create(app)
    assert created.id == app.id

    fetched = await repo.get_by_id(app.id)
    assert fetched is not None
    assert fetched.id == app.id

    fetched_user_job = await repo.get_by_user_and_job(app.user_id, app.job_id)
    assert fetched_user_job is not None
    assert fetched_user_job.id == app.id

    fetched_idmp = await repo.get_by_idempotency_key(app.idempotency_key)
    assert fetched_idmp is not None
    assert fetched_idmp.id == app.id


@pytest.mark.asyncio
async def test_repo_idempotent_creation(repo):
    """Calling create() with same idempotency_key for same (user_id, job_id) safely returns existing."""
    app = make_app()
    first = await repo.create(app)

    # Replay with same idempotency key and same user/job
    second = await repo.create(app)
    assert second.id == first.id


@pytest.mark.asyncio
async def test_repo_enforces_unique_user_job_constraint(repo):
    """UNIQUE(user_id, job_id) rejects second application for same user and job."""
    u_id = uuid4()
    j_id = uuid4()
    app1 = make_app(user_id=u_id, job_id=j_id, idempotency_key="idmp_1")
    await repo.create(app1)

    app2 = make_app(user_id=u_id, job_id=j_id, idempotency_key="idmp_2")
    with pytest.raises(DuplicateApplicationError):
        await repo.create(app2)


@pytest.mark.asyncio
async def test_repo_enforces_unique_idempotency_key_constraint(repo):
    """UNIQUE(idempotency_key) rejects different user/job with colliding key."""
    app1 = make_app(idempotency_key="collision_key")
    await repo.create(app1)

    app2 = make_app(idempotency_key="collision_key")
    with pytest.raises(IdempotencyConflictError):
        await repo.create(app2)


@pytest.mark.asyncio
async def test_repo_preserves_separate_job_requisitions(repo):
    """Distinct job requisitions for the same user are created independently without merging."""
    u_id = uuid4()
    app1 = make_app(user_id=u_id, external_id="req-101")
    app2 = make_app(user_id=u_id, external_id="req-102")

    created1 = await repo.create(app1)
    created2 = await repo.create(app2)

    assert created1.id != created2.id
    assert created1.job_id != created2.job_id


@pytest.mark.asyncio
async def test_repo_update_and_missing(repo):
    app = make_app()
    await repo.create(app)

    updated_app = app.model_copy(update={"status": ApplicationStatus.MATCHED, "score": 88.0})
    res = await repo.update(updated_app)
    assert res.status == ApplicationStatus.MATCHED
    assert res.score == 88.0

    missing_app = make_app()
    with pytest.raises(ApplicationNotFoundError):
        await repo.update(missing_app)


@pytest.mark.asyncio
async def test_repo_list_and_count(repo):
    u_id = uuid4()
    app_disc = make_app(user_id=u_id, status=ApplicationStatus.DISCOVERED)
    app_match = make_app(user_id=u_id, status=ApplicationStatus.MATCHED)
    await repo.create(app_disc)
    await repo.create(app_match)

    disc_list = await repo.list_by_status(ApplicationStatus.DISCOVERED)
    assert len(disc_list) == 1
    assert disc_list[0].id == app_disc.id

    user_list = await repo.list_by_user(u_id)
    assert len(user_list) == 2

    assert await repo.count() == 2
    assert await repo.count(status=ApplicationStatus.MATCHED) == 1
    assert await repo.count(user_id=u_id) == 2


@pytest.mark.asyncio
async def test_event_repo_append_and_list(event_repo):
    app_id = uuid4()
    now1 = datetime(2026, 11, 15, 10, 0, 0, tzinfo=timezone.utc)
    now2 = datetime(2026, 11, 15, 10, 5, 0, tzinfo=timezone.utc)

    ev1 = ApplicationEvent(
        application_id=app_id,
        event_type="CREATED",
        previous_status=None,
        new_status=ApplicationStatus.DISCOVERED,
        timestamp=now1,
    )
    ev2 = ApplicationEvent(
        application_id=app_id,
        event_type="MATCH_EVALUATED",
        previous_status=ApplicationStatus.DISCOVERED,
        new_status=ApplicationStatus.MATCHED,
        timestamp=now2,
    )

    await event_repo.append_event(ev1)
    await event_repo.append_event(ev2)

    events = await event_repo.list_by_application_id(app_id)
    assert len(events) == 2
    assert events[0].event_type == "CREATED"
    assert events[1].event_type == "MATCH_EVALUATED"
    assert events[0].timestamp < events[1].timestamp
