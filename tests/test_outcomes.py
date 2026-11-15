"""Unit tests for Application Outcome Milestone Tracking and API Endpoints (Phase 1.9).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 13, 14)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from services.api.main import create_app
from worker.application.models import Application, ApplicationStatus
from worker.application.outcomes import (
    ApplicationOutcomeRecord,
    OutcomeMilestone,
    OutcomeTracker,
)
from worker.application.repository import InMemoryApplicationRepository


def test_outcome_tracker_lifecycle(tmp_path: Path):
    storage_file = tmp_path / "outcomes.json"
    tracker = OutcomeTracker(storage_path=storage_file)

    app_id = str(uuid4())

    # 1. Record Interview
    r1 = tracker.record_milestone(
        application_id=app_id,
        milestone=OutcomeMilestone.INTERVIEW_SCHEDULED,
        event_timestamp=datetime(2026, 4, 10, 15, 0, tzinfo=timezone.utc),
        notes="First round technical screen with hiring manager",
        recruiter_contact="recruiter@example.com",
    )

    assert r1.application_id == app_id
    assert r1.milestone == OutcomeMilestone.INTERVIEW_SCHEDULED

    # 2. Record Offer
    r2 = tracker.record_milestone(
        application_id=app_id,
        milestone=OutcomeMilestone.OFFER_RECEIVED,
        offer_amount=165000.0,
        notes="Base salary $165k with equity",
    )
    assert r2.milestone == OutcomeMilestone.OFFER_RECEIVED
    assert r2.offer_amount == 165000.0

    # 3. Retrieve milestones for application
    outcomes = tracker.get_outcomes_for_application(app_id)
    assert len(outcomes) == 2
    assert outcomes[0].milestone == OutcomeMilestone.INTERVIEW_SCHEDULED
    assert outcomes[1].milestone == OutcomeMilestone.OFFER_RECEIVED


def test_outcome_api_endpoints():
    from services.api.dependencies import get_application_repository
    from services.api.config import Settings

    app_repo = InMemoryApplicationRepository()
    dev_settings = Settings(allow_tokenless_dev=True, api_host="127.0.0.1")
    app = create_app(dev_settings)
    app.dependency_overrides[get_application_repository] = lambda: app_repo
    client = TestClient(app)

    # Pre-seed application in repository
    app_id = uuid4()
    dummy_app = Application(
        id=app_id,
        user_id=uuid4(),
        job_id=uuid4(),
        status=ApplicationStatus.APPLIED,
        idempotency_key="key_12345",
        platform="greenhouse",
        external_id="ext_outcome_1",
        profile_version="v1.0-test",
    )
    import asyncio
    asyncio.run(app_repo.create(dummy_app))

    # 1. POST /api/v1/applications/{id}/outcomes
    resp = client.post(
        f"/api/v1/applications/{app_id}/outcomes",
        json={
            "milestone": "TECHNICAL_SCREEN",
            "notes": "Completed live coding interview",
            "recruiter_contact": "sarah@techcorp.com",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["milestone"] == "TECHNICAL_SCREEN"
    assert data["application_id"] == str(app_id)

    # 2. GET /api/v1/applications/{id}/outcomes
    list_resp = client.get(f"/api/v1/applications/{app_id}/outcomes")
    assert list_resp.status_code == 200
    milestones = list_resp.json()
    assert len(milestones) >= 1
    assert milestones[-1]["milestone"] == "TECHNICAL_SCREEN"

    # 3. 404 for unknown application
    unknown_id = uuid4()
    err_resp = client.post(
        f"/api/v1/applications/{unknown_id}/outcomes",
        json={"milestone": "OFFER_RECEIVED"},
    )
    assert err_resp.status_code == 404
