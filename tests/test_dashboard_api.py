"""Integration tests for Dashboard API endpoints (Phase 2.4)."""

from uuid import uuid4
import pytest
from starlette.testclient import TestClient

from services.api.dependencies import get_application_event_repository, get_application_repository
from services.api.main import app
from worker.application.models import (
    Application,
    ApplicationEvent,
    ApplicationEventType,
    ApplicationStatus,
    AutonomyLevel,
)
from worker.application.repository import (
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)


@pytest.fixture
def dashboard_client():
    app_repo = InMemoryApplicationRepository()
    event_repo = InMemoryApplicationEventRepository()

    app.dependency_overrides[get_application_repository] = lambda: app_repo
    app.dependency_overrides[get_application_event_repository] = lambda: event_repo

    with TestClient(app) as client:
        yield client, app_repo, event_repo

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_overview_and_queues(dashboard_client):
    client, app_repo, event_repo = dashboard_client
    user_id = uuid4()
    headers = {
        "Authorization": f"Bearer user-jwt-{user_id}",
        "X-User-ID": str(user_id),
        "X-User-Role": "OWNER",
    }

    # 1. Populate applications
    app1 = Application(
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="gh-101",
        profile_version="v2.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="idmp-app-1",
    )
    app2 = Application(
        user_id=user_id,
        job_id=uuid4(),
        platform="lever",
        external_id="lev-202",
        profile_version="v2.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.DRY_RUN_DONE,
        idempotency_key="idmp-app-2",
    )
    await app_repo.create(app1)
    await app_repo.create(app2)

    # 2. Test /overview
    resp = client.get("/api/v1/dashboard/overview", headers=headers)
    assert resp.status_code == 200
    ov = resp.json()
    assert ov["jobs_discovered"] == 2
    assert ov["applications_awaiting_approval"] == 1
    assert ov["dry_runs_completed"] == 1
    assert ov["real_submit_gate_locked"] is True

    # 3. Test /applications queue
    apps_resp = client.get("/api/v1/dashboard/applications", headers=headers)
    assert apps_resp.status_code == 200
    paged = apps_resp.json()
    assert paged["total"] == 2
    assert len(paged["items"]) == 2

    # 4. Test /approvals queue
    appr_resp = client.get("/api/v1/dashboard/approvals", headers=headers)
    assert appr_resp.status_code == 200
    approvals = appr_resp.json()
    assert len(approvals) == 1
    assert approvals[0]["id"] == str(app1.id)

    # 5. Test /analytics
    ana_resp = client.get("/api/v1/dashboard/analytics", headers=headers)
    assert ana_resp.status_code == 200
    ana = ana_resp.json()
    assert ana["discovered"] == 2
    assert ana["awaiting_approval"] == 1
    assert ana["dry_run_done"] == 1
    assert ana["applied_live"] == 0  # Hardcoded invariant in L0


@pytest.mark.asyncio
async def test_dashboard_timeline_and_ownership(dashboard_client):
    client, app_repo, event_repo = dashboard_client
    owner_id = uuid4()
    stranger_id = uuid4()

    app_record = Application(
        user_id=owner_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="gh-303",
        profile_version="v2.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.DISCOVERED,
        idempotency_key="idmp-app-3",
    )
    await app_repo.create(app_record)

    event = ApplicationEvent(
        application_id=app_record.id,
        event_type=ApplicationEventType.CREATED.value,
        reason="Discovered through public board",
    )
    await event_repo.append_event(event)

    # 1. Owner can fetch detail and timeline
    owner_headers = {
        "Authorization": f"Bearer user-jwt-{owner_id}",
        "X-User-ID": str(owner_id),
        "X-User-Role": "OWNER",
    }
    detail_resp = client.get(f"/api/v1/dashboard/applications/{app_record.id}", headers=owner_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == str(app_record.id)

    timeline_resp = client.get(f"/api/v1/dashboard/applications/{app_record.id}/timeline", headers=owner_headers)
    assert timeline_resp.status_code == 200
    events = timeline_resp.json()
    assert len(events) == 1
    assert events[0]["event_type"] == ApplicationEventType.CREATED.value

    # 2. Stranger gets 403 Forbidden on detail and timeline
    stranger_headers = {
        "Authorization": f"Bearer user-jwt-{stranger_id}",
        "X-User-ID": str(stranger_id),
        "X-User-Role": "OWNER",
    }
    denied = client.get(f"/api/v1/dashboard/applications/{app_record.id}", headers=stranger_headers)
    assert denied.status_code == 403

    denied_timeline = client.get(f"/api/v1/dashboard/applications/{app_record.id}/timeline", headers=stranger_headers)
    assert denied_timeline.status_code == 403
