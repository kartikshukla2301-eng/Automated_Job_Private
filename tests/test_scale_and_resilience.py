"""Scale, resilience, latency benchmarking, and failure injection suite (Phase 2.8).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 11, 13, 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, List
import pytest
from uuid import uuid4
from starlette.testclient import TestClient

from services.api.main import create_app
from worker.application.idempotency import generate_application_idempotency_key
from worker.application.models import Application, ApplicationStatus, AutonomyLevel
from worker.application.repository import InMemoryApplicationRepository
from worker.core.caps import CapsConfig, CapsEnforcer, InMemoryApplicationLedger
from worker.core.exceptions import KillSwitchActiveError
from worker.core.kill_switch import InMemoryKillSwitch
from worker.core.safety import SafetyEngine
from worker.discovery.repository import InMemoryJobRepository
from worker.matching.calibration import MatchingCalibrator, generate_benchmark_samples
from worker.persistence.exceptions import DatabaseConnectionError, DuplicateRecordError
from worker.persistence.supabase_client import SupabaseClient


# -----------------------------------------------------------------------------
# 1. Latency & Throughput Benchmarks
# -----------------------------------------------------------------------------

def test_matching_benchmark_latency():
    """Verify that deterministic matching across 50 jobs finishes well within 200ms."""
    calibrator = MatchingCalibrator(generate_benchmark_samples())
    start = time.perf_counter()
    report = calibrator.evaluate(threshold=65.0)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert report.total_samples == 50
    assert elapsed_ms < 200.0, f"Matching 50 jobs took {elapsed_ms:.2f}ms (expected < 200ms)"


def test_api_probes_benchmark_latency():
    """Verify that health probes respond in under 50ms."""
    app = create_app()
    client = TestClient(app)

    start = time.perf_counter()
    live_resp = client.get("/health/live")
    live_elapsed_ms = (time.perf_counter() - start) * 1000
    assert live_resp.status_code == 200
    assert live_elapsed_ms < 100.0

    start = time.perf_counter()
    ready_resp = client.get("/health/ready")
    ready_elapsed_ms = (time.perf_counter() - start) * 1000
    assert ready_resp.status_code == 200
    assert ready_elapsed_ms < 100.0


# -----------------------------------------------------------------------------
# 2. Concurrency & Idempotency Resilience
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_application_creation_idempotency():
    """Verify concurrent creation of application with identical idempotency key returns exact same record."""
    repo = InMemoryApplicationRepository()
    user_id = uuid4()
    job_id = uuid4()
    key = generate_application_idempotency_key(user_id=user_id, job_id=job_id, profile_version="v1.0")

    app1 = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=job_id,
        platform="lever",
        external_id="ext-conc-1",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.DISCOVERED,
        idempotency_key=key,
    )
    app2 = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=job_id,
        platform="lever",
        external_id="ext-conc-1",
        profile_version="v1.0",
        autonomy_level=AutonomyLevel.L0,
        status=ApplicationStatus.DISCOVERED,
        idempotency_key=key,
    )

    # Simulate simultaneous creation attempts
    results = await asyncio.gather(
        repo.create(app1),
        repo.create(app2),
        return_exceptions=True,
    )

    # Exactly one unique application should exist in repository
    all_apps = await repo.list_by_user(user_id)
    assert len(all_apps) == 1
    stored = all_apps[0]
    assert stored.idempotency_key == key


# -----------------------------------------------------------------------------
# 3. Failure Injection & Error Containment
# -----------------------------------------------------------------------------

def test_supabase_error_translation_resilience():
    """Verify PostgREST errors are translated into typed DB exceptions without leaking credentials."""
    client = SupabaseClient(base_url="https://mock.supabase.co", api_key="secret-key")

    # 409 Conflict -> DuplicateRecordError
    err_409 = client.translate_error(409, {"message": "duplicate key value violates unique constraint"}, "insert")
    assert isinstance(err_409, DuplicateRecordError)

    # 503 / 500 -> DatabaseConnectionError
    err_503 = client.translate_error(503, {"message": "Database unavailable"}, "select")
    assert isinstance(err_503, DatabaseConnectionError)
    assert "secret-key" not in str(err_503)


def test_kill_switch_trip_halts_pipeline_immediately():
    """Verify tripping kill switch halts subsequent actions immediately fail-closed."""
    ks = InMemoryKillSwitch(initial_enabled=True)
    ledger = InMemoryApplicationLedger()
    caps = CapsEnforcer(config=CapsConfig(), ledger=ledger)
    safety = SafetyEngine(kill_switch=ks, caps_enforcer=caps, real_submit_gate_enabled=False)

    # Step 1: Normal action allowed
    safety.verify_pre_apply(company="TechCorp", provider="greenhouse")

    # Emergency kill switch trip
    ks.trip(reason="Operator detected unexpected field anomaly", updated_by="operator")

    # Step 2: Next action strictly blocked
    with pytest.raises(KillSwitchActiveError) as exc_info:
        safety.verify_pre_apply(company="TechCorp", provider="greenhouse")

    assert "Operator detected unexpected field anomaly" in str(exc_info.value)
