"""Integration tests for Pilot API routes (Phase 2.1)."""

from pathlib import Path
from uuid import uuid4
import pytest
from starlette.testclient import TestClient

from services.api.main import app
from services.api.routes.pilot import get_pilot_orchestrator
from worker.pilot.evidence import PilotEvidenceManager
from worker.pilot.models import PilotReviewStatus
from worker.pilot.orchestrator import PilotOrchestrator


@pytest.fixture
def client_with_pilot(tmp_path: Path):
    ev_dir = tmp_path / "evidence"
    storage_path = tmp_path / "records.json"
    ev_mgr = PilotEvidenceManager(base_evidence_dir=ev_dir)
    test_orchestrator = PilotOrchestrator(
        evidence_manager=ev_mgr,
        records_storage_path=storage_path,
    )
    app.dependency_overrides[get_pilot_orchestrator] = lambda: test_orchestrator

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_pilot_api_workflow(client_with_pilot: TestClient):
    user_id = str(uuid4())

    # 1. Inspect form
    resp = client_with_pilot.post(
        "/api/v1/pilot/inspect",
        json={
            "user_id": user_id,
            "provider": "greenhouse",
            "job_url": "https://boards.greenhouse.io/demo/jobs/999",
            "company": "Demo Corp",
            "title": "Backend Architect",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    record_id = data["id"]
    assert data["company"] == "Demo Corp"
    assert data["review_status"] == "PENDING"

    # 2. List records
    list_resp = client_with_pilot.get(f"/api/v1/pilot/records?user_id={user_id}")
    assert list_resp.status_code == 200
    records = list_resp.json()
    assert len(records) == 1
    assert records[0]["id"] == record_id

    # 3. Get single record
    get_resp = client_with_pilot.get(f"/api/v1/pilot/records/{record_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == record_id

    # 4. Submit human review
    review_resp = client_with_pilot.post(
        f"/api/v1/pilot/records/{record_id}/review",
        json={
            "status": "APPROVED",
            "reviewer_id": "auditor_1",
            "notes": "Verified against candidate resume",
            "incorrect_mappings_count": 0,
            "wrong_sensitive_count": 0,
        },
    )
    assert review_resp.status_code == 200
    reviewed_data = review_resp.json()
    assert reviewed_data["review_status"] == "APPROVED"
    assert reviewed_data["reviewer_id"] == "auditor_1"

    # 5. Check metrics endpoint
    metrics_resp = client_with_pilot.get("/api/v1/pilot/metrics")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert metrics["total_inspections"] == 1
    assert metrics["forms_reviewed"] == 1
    assert metrics["reviewed_field_accuracy"] >= 0.0
