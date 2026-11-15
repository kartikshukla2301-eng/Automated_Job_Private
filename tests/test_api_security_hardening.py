"""Comprehensive API security, authorization, and rate limiting hardening tests (Phase 2.3)."""

from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from services.api.config import Settings
from services.api.main import app, create_app
from services.api.security.auth import (
    get_authenticated_subject,
    require_owner_or_operator,
    require_worker_identity,
    verify_application_ownership,
)
from services.api.security.models import AuthenticatedSubject, UserRole
from services.api.security.rate_limiter import SlidingWindowRateLimiter
from worker.application.models import Application, ApplicationStatus, AutonomyLevel


def test_health_and_probes():
    with TestClient(app) as client:
        # 1. Base /health
        h = client.get("/health")
        assert h.status_code == 200
        assert h.json()["status"] == "healthy"

        # 2. Liveness /health/live
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "alive"

        # 3. Readiness /health/ready
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["real_submit_gate_locked"] is True


def test_auth_subject_classification():
    settings = Settings(
        worker_token="prod-worker-secret-999",
        app_env="production",
        api_host="0.0.0.0",
        allow_tokenless_dev=False,
    )

    # 1. Missing token in prod -> 401
    with pytest.raises(HTTPException) as exc_info:
        get_authenticated_subject(
            authorization=None,
            x_worker_token=None,
            x_user_jwt=None,
            app_settings=settings,
        )
    assert exc_info.value.status_code == 401

    # 2. Valid worker token -> WORKER role
    subj_worker = get_authenticated_subject(
        x_worker_token="prod-worker-secret-999",
        app_settings=settings,
    )
    assert subj_worker.role == UserRole.WORKER
    assert subj_worker.token_type == "worker_token"

    # 3. Valid user JWT -> OWNER role
    user_id = uuid4()
    subj_user = get_authenticated_subject(
        authorization=f"Bearer user-jwt-{user_id}",
        app_settings=settings,
    )
    assert subj_user.role == UserRole.OWNER
    assert subj_user.subject_id == user_id


def test_role_boundary_enforcement():
    worker_subj = AuthenticatedSubject(
        subject_id=uuid4(),
        role=UserRole.WORKER,
        token_type="worker_token",
    )
    user_subj = AuthenticatedSubject(
        subject_id=uuid4(),
        role=UserRole.OWNER,
        token_type="user_jwt",
    )

    # 1. Worker attempting operator action -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        require_owner_or_operator(worker_subj)
    assert exc_info.value.status_code == 403
    assert "not authorized for operator actions" in str(exc_info.value.detail)

    # 2. User executing operator action -> Allowed
    assert require_owner_or_operator(user_subj) == user_subj

    # 3. User attempting worker queue action -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info2:
        require_worker_identity(user_subj)
    assert exc_info2.value.status_code == 403
    assert "not authorized for internal worker execution" in str(exc_info2.value.detail)

    # 4. Worker executing worker queue action -> Allowed
    assert require_worker_identity(worker_subj) == worker_subj


def test_cross_user_ownership_violation_blocked():
    owner_id = uuid4()
    stranger_id = uuid4()

    app = Application(
        user_id=owner_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="gh-1",
        profile_version="v2.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.DISCOVERED,
        idempotency_key="idmp-owner-1",
    )

    owner_subject = AuthenticatedSubject(subject_id=owner_id, role=UserRole.OWNER)
    stranger_subject = AuthenticatedSubject(subject_id=stranger_id, role=UserRole.OWNER)
    worker_subject = AuthenticatedSubject(subject_id=uuid4(), role=UserRole.WORKER)

    # 1. Owner can access their own application
    verify_application_ownership(app, owner_subject)

    # 2. Worker can access for automated queues
    verify_application_ownership(app, worker_subject)

    # 3. Cross-user access is strictly blocked with 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        verify_application_ownership(app, stranger_subject)
    assert exc_info.value.status_code == 403
    assert "do not have permission" in str(exc_info.value.detail)


def test_sliding_window_rate_limiter():
    limiter = SlidingWindowRateLimiter()
    key = "test-client-ip"

    # Allow up to 3 requests per 60 seconds
    allowed1, rem1, _ = limiter.check_rate_limit(key, limit=3, window_seconds=60)
    assert allowed1 is True
    assert rem1 == 2

    allowed2, rem2, _ = limiter.check_rate_limit(key, limit=3, window_seconds=60)
    assert allowed2 is True
    assert rem2 == 1

    allowed3, rem3, _ = limiter.check_rate_limit(key, limit=3, window_seconds=60)
    assert allowed3 is True
    assert rem3 == 0

    # 4th request must be rejected
    allowed4, rem4, reset_secs = limiter.check_rate_limit(key, limit=3, window_seconds=60)
    assert allowed4 is False
    assert rem4 == 0
    assert reset_secs > 0
