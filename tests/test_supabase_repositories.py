"""Comprehensive tests for Supabase repositories, RLS, storage, and idempotency (Phase 2.2)."""

from datetime import datetime, timezone
import json
from uuid import UUID, uuid4
import httpx
import pytest

from worker.application.exceptions import (
    ApplicationNotFoundError,
    DuplicateApplicationError,
    IdempotencyConflictError,
)
from worker.application.models import (
    Application,
    ApplicationEvent,
    ApplicationEventType,
    ApplicationStatus,
    AutonomyLevel,
)
from worker.discovery.models import Job, JobStatus
from worker.persistence.application_repository import SupabaseApplicationRepository
from worker.persistence.event_repository import SupabaseApplicationEventRepository
from worker.persistence.exceptions import (
    AuthorizationError,
    DatabaseConnectionError,
    DuplicateRecordError,
    RecordNotFoundError,
    StorageError,
)
from worker.persistence.job_repository import SupabaseJobRepository
from worker.persistence.storage import SupabaseStorageService
from worker.persistence.supabase_client import SupabaseClient


# In-memory mock PostgREST transport for isolated database testing
class MockPostgrestTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.tables = {
            "applications": {},
            "application_events": [],
            "jobs": {},
            "answer_bank": {},
        }

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url_path = request.url.path
        parts = url_path.strip("/").split("/")
        
        # Check storage mock
        if "storage" in parts:
            if "object" in parts and request.method == "POST":
                if "sign" in parts:
                    return httpx.Response(200, json={"signedURL": "/storage/v1/object/sign/evidence/test.png?token=exp-123"})
                return httpx.Response(201, json={"Key": "evidence/test.png"})
            return httpx.Response(404, text="Not Found")

        table = parts[-1]
        params = dict(request.url.params)

        # RLS authorization check test
        if request.headers.get("Authorization") == "Bearer invalid-jwt":
            return httpx.Response(403, json={"code": "42501", "message": "RLS policy violation: permission denied"})

        if request.method == "POST":
            payload = json.loads(request.content.decode("utf-8"))
            if table == "applications":
                app_id = payload["id"]
                user_id = payload["user_id"]
                job_id = payload["job_id"]
                idmp = payload.get("idempotency_key")

                # Check unique constraints
                for existing in self.tables["applications"].values():
                    if existing["idempotency_key"] == idmp:
                        return httpx.Response(409, json={"code": "23505", "message": "duplicate key value violates unique constraint uq_applications_idempotency"})
                    if existing["user_id"] == user_id and existing["job_id"] == job_id:
                        return httpx.Response(409, json={"code": "23505", "message": "duplicate key value violates unique constraint uq_applications_user_job"})

                self.tables["applications"][app_id] = payload
                return httpx.Response(201, json=[payload])

            elif table == "application_events":
                self.tables["application_events"].append(payload)
                return httpx.Response(201, json=[payload])

            elif table == "jobs":
                job_id = payload["id"]
                self.tables["jobs"][job_id] = payload
                return httpx.Response(201, json=[payload])

        elif request.method == "GET":
            if table == "applications":
                results = list(self.tables["applications"].values())
                if "id" in params:
                    target_id = params["id"].replace("eq.", "")
                    results = [r for r in results if r["id"] == target_id]
                if "user_id" in params:
                    uid = params["user_id"].replace("eq.", "")
                    results = [r for r in results if r["user_id"] == uid]
                if "job_id" in params:
                    jid = params["job_id"].replace("eq.", "")
                    results = [r for r in results if r["job_id"] == jid]
                if "status" in params:
                    st = params["status"].replace("eq.", "")
                    results = [r for r in results if r["status"] == st]
                if "idempotency_key" in params:
                    k = params["idempotency_key"].replace("eq.", "")
                    results = [r for r in results if r["idempotency_key"] == k]
                return httpx.Response(200, json=results)

            elif table == "application_events":
                results = list(self.tables["application_events"])
                if "application_id" in params:
                    aid = params["application_id"].replace("eq.", "")
                    results = [r for r in results if r["application_id"] == aid]
                return httpx.Response(200, json=results)

            elif table == "jobs":
                results = list(self.tables["jobs"].values())
                if "id" in params:
                    target_id = params["id"].replace("eq.", "")
                    results = [r for r in results if r["id"] == target_id]
                if "canonical_key" in params:
                    ck = params["canonical_key"].replace("eq.", "")
                    results = [r for r in results if r["canonical_key"] == ck]
                if "platform" in params and "external_id" in params:
                    p = params["platform"].replace("eq.", "")
                    e = params["external_id"].replace("eq.", "")
                    results = [r for r in results if r["platform"] == p and r["external_id"] == e]
                return httpx.Response(200, json=results)

        elif request.method == "PATCH":
            payload = json.loads(request.content.decode("utf-8"))
            if table == "applications":
                target_id = params.get("id", "").replace("eq.", "")
                if target_id in self.tables["applications"]:
                    self.tables["applications"][target_id].update(payload)
                    return httpx.Response(200, json=[self.tables["applications"][target_id]])
                return httpx.Response(200, json=[])

            elif table == "jobs":
                target_id = params.get("id", "").replace("eq.", "")
                if target_id in self.tables["jobs"]:
                    self.tables["jobs"][target_id].update(payload)
                    return httpx.Response(200, json=[self.tables["jobs"][target_id]])
                return httpx.Response(200, json=[])

        return httpx.Response(200, json=[])


@pytest.fixture
def mock_supabase_client():
    transport = MockPostgrestTransport()
    async_client = httpx.AsyncClient(transport=transport)
    return SupabaseClient(base_url="http://mock.supabase.local", client=async_client)


@pytest.mark.asyncio
async def test_supabase_client_authorization_error(mock_supabase_client: SupabaseClient):
    """Verify RLS authorization violations raise typed AuthorizationError."""
    with pytest.raises(AuthorizationError):
        await mock_supabase_client.select("applications", jwt="invalid-jwt")


@pytest.mark.asyncio
async def test_supabase_application_repository_lifecycle(mock_supabase_client: SupabaseClient):
    repo = SupabaseApplicationRepository(client=mock_supabase_client)

    user_id = uuid4()
    job_id = uuid4()
    app = Application(
        user_id=user_id,
        job_id=job_id,
        platform="greenhouse",
        external_id="12345",
        profile_version="v2.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.DISCOVERED,
        idempotency_key="idmp-key-001",
    )

    # 1. Create Application
    created = await repo.create(app)
    assert created.id == app.id
    assert created.status == ApplicationStatus.DISCOVERED

    # 2. Get by ID and Unique Constraints
    by_id = await repo.get_by_id(app.id)
    assert by_id is not None
    assert by_id.id == app.id

    by_uj = await repo.get_by_user_and_job(user_id, job_id)
    assert by_uj is not None
    assert by_uj.id == app.id

    by_idmp = await repo.get_by_idempotency_key("idmp-key-001")
    assert by_idmp is not None

    # 3. Idempotency replay returns existing safely
    replay = await repo.create(app)
    assert replay.id == app.id

    # 4. Conflicting idempotency key for different job raises IdempotencyConflictError
    conflicting_app = Application(
        user_id=user_id,
        job_id=uuid4(),  # Different job
        platform="greenhouse",
        external_id="different-ext",
        profile_version="v2.0",
        idempotency_key="idmp-key-001",  # Same key
    )
    with pytest.raises(IdempotencyConflictError):
        await repo.create(conflicting_app)

    # 5. Duplicate (user_id, job_id) raises DuplicateApplicationError
    dup_app = Application(
        user_id=user_id,
        job_id=job_id,
        platform="greenhouse",
        external_id="different-idmp",
        profile_version="v2.0",
        idempotency_key="idmp-different",
    )
    with pytest.raises(DuplicateApplicationError):
        await repo.create(dup_app)

    # 6. Update application
    updated = app.model_copy(update={"status": ApplicationStatus.MATCHED})
    res_update = await repo.update(updated)
    assert res_update.status == ApplicationStatus.MATCHED

    # 7. List and Count
    user_apps = await repo.list_by_user(user_id=user_id)
    assert len(user_apps) == 1
    cnt = await repo.count(user_id=user_id)
    assert cnt == 1


@pytest.mark.asyncio
async def test_supabase_event_repository(mock_supabase_client: SupabaseClient):
    repo = SupabaseApplicationEventRepository(client=mock_supabase_client)
    app_id = uuid4()

    event1 = ApplicationEvent(
        application_id=app_id,
        event_type=ApplicationEventType.CREATED.value,
        reason="Discovered job record",
        triggering_component="DiscoveryAdapter",
    )
    event2 = ApplicationEvent(
        application_id=app_id,
        event_type=ApplicationEventType.STATE_TRANSITION.value,
        previous_status=ApplicationStatus.DISCOVERED,
        new_status=ApplicationStatus.MATCHED,
        reason="Match score 85.0",
        triggering_component="MatchingEngine",
    )

    await repo.append_event(event1)
    await repo.append_event(event2)

    history = await repo.list_by_application_id(app_id)
    assert len(history) == 2
    assert history[0].event_type == ApplicationEventType.CREATED.value
    assert history[1].new_status == ApplicationStatus.MATCHED


@pytest.mark.asyncio
async def test_supabase_job_repository(mock_supabase_client: SupabaseClient):
    import hashlib
    repo = SupabaseJobRepository(client=mock_supabase_client)

    desc = "Build scalable microservices in Python"
    ch = hashlib.sha256(desc.encode()).hexdigest()
    job = Job(
        platform="greenhouse",
        external_id="gh-777",
        canonical_key="acme:backend-eng:senior",
        company="Acme Corp",
        normalized_company="acme corp",
        title="Senior Backend Engineer",
        normalized_title="senior backend engineer",
        url="https://boards.greenhouse.io/acme/jobs/777",
        description=desc,
        content_hash=ch,
    )

    # 1. Save Job
    saved = await repo.save(job)
    assert saved.id == job.id

    # 2. Get by canonical key
    matched = await repo.get_by_canonical_key("acme:backend-eng:senior")
    assert len(matched) == 1

    # 3. Update score
    updated = await repo.update_score(job.id, score=92.5, score_breakdown={"skills": 30.0})
    assert updated is not None
    assert updated.score == 92.5


@pytest.mark.asyncio
async def test_supabase_storage_service(mock_supabase_client: SupabaseClient):
    storage = SupabaseStorageService(
        base_url="http://mock.supabase.local",
        client=mock_supabase_client._external_client,
    )

    # 1. Rejects disallowed mime types
    with pytest.raises(StorageError, match="Unsupported content type"):
        storage.validate_file(b"bad content", "application/x-executable")

    # 2. Rejects oversized files
    huge_image = b"x" * (6 * 1024 * 1024)  # 6 MB (max allowed for png is 5MB)
    with pytest.raises(StorageError, match="exceeds maximum allowed size"):
        storage.validate_file(huge_image, "image/png")

    # 3. Valid upload and signed URL generation
    valid_screenshot = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    path = await storage.upload("evidence", "run-1/screenshot.png", valid_screenshot, "image/png")
    assert path == "run-1/screenshot.png"

    signed_url = await storage.create_signed_url("evidence", path, expires_in=600)
    assert "signedURL" in signed_url or "token=" in signed_url
