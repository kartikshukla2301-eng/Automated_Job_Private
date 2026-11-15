"""Unit tests for PilotOrchestrator, evidence management, and human review (Phase 2.1)."""

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
import pytest
from unittest.mock import AsyncMock, MagicMock

import yaml
from worker.pilot.evidence import PilotEvidenceManager, sanitize_dict_pii, sanitize_pii
from worker.pilot.models import PilotReviewRequest, PilotReviewStatus
from worker.pilot.orchestrator import PilotOrchestrator
from worker.profile.models import ProfileSnapshot


@pytest.fixture
def test_profile_snapshot():
    raw = yaml.safe_load(Path("fixtures/profile.yaml").read_text(encoding="utf-8"))
    return ProfileSnapshot.model_validate(raw)


def test_sanitize_pii_and_dict():
    raw_text = "Contact me at candidate@example.com or +1-555-0199, SSN: 000-12-3456"
    sanitized = sanitize_pii(raw_text)
    assert "[REDACTED_EMAIL]" in sanitized
    assert "[REDACTED_PHONE]" in sanitized
    assert "[REDACTED_SSN]" in sanitized

    raw_dict = {
        "email": "user@example.com",
        "api_key": "secret-token-1234",
        "nested": {
            "password": "super-secret-password",
            "phone": "+1-555-0100",
        },
    }
    san_dict = sanitize_dict_pii(raw_dict)
    assert san_dict["email"] == "[REDACTED_EMAIL]"
    assert san_dict["api_key"] == "[REDACTED_SECRET]"
    assert san_dict["nested"]["password"] == "[REDACTED_SECRET]"
    assert san_dict["nested"]["phone"] == "[REDACTED_PHONE]"


@pytest.mark.asyncio
async def test_pilot_orchestrator_inspection_and_evidence(tmp_path: Path, test_profile_snapshot):
    evidence_dir = tmp_path / "evidence"
    storage_path = tmp_path / "pilot_records.json"
    ev_mgr = PilotEvidenceManager(base_evidence_dir=evidence_dir)
    orchestrator = PilotOrchestrator(
        evidence_manager=ev_mgr,
        records_storage_path=storage_path,
    )

    fixture_path = Path("fixtures/forms/greenhouse_job.html").resolve()
    assert fixture_path.exists()
    html_content = fixture_path.read_text(encoding="utf-8")

    user_id = uuid4()
    record = await orchestrator.inspect_form(
        user_id=user_id,
        provider_name="greenhouse",
        job_url="https://boards.greenhouse.io/acme/jobs/12345",
        company="Acme Corp",
        title="Software Engineer",
        profile=test_profile_snapshot,
        html_content=html_content,
        is_live_page=False,
    )

    assert record.company == "Acme Corp"
    assert record.fields_count >= 5
    assert record.resolved_count > 0
    assert record.review_status == PilotReviewStatus.PENDING
    assert record.audit_hash is not None

    # Verify evidence stored on disk
    rec_evidence = Path(record.evidence_dir)
    assert rec_evidence.exists()
    assert (rec_evidence / "form_schema.json").exists()
    assert (rec_evidence / "fill_plan.json").exists()
    assert (rec_evidence / "metadata.json").exists()

    # Verify retrieval
    fetched = orchestrator.get_record(record.id)
    assert fetched is not None
    assert fetched.id == record.id


@pytest.mark.asyncio
async def test_pilot_human_review_and_gate_readiness(tmp_path: Path, test_profile_snapshot):
    evidence_dir = tmp_path / "evidence"
    storage_path = tmp_path / "pilot_records.json"
    ev_mgr = PilotEvidenceManager(base_evidence_dir=evidence_dir)
    orchestrator = PilotOrchestrator(
        evidence_manager=ev_mgr,
        records_storage_path=storage_path,
    )

    html_content = Path("fixtures/forms/greenhouse_job.html").read_text(encoding="utf-8")
    user_id = uuid4()

    # 1. Create 20 distinct pilot form records
    records = []
    for i in range(20):
        rec = await orchestrator.inspect_form(
            user_id=user_id,
            provider_name="greenhouse",
            job_url=f"https://boards.greenhouse.io/acme/jobs/100{i}",
            company="Acme Corp",
            title=f"Engineer {i}",
            profile=test_profile_snapshot,
            html_content=html_content,
        )
        records.append(rec)

    # Initial report: forms unreviewed -> Gate NOT ready
    report = orchestrator.generate_quality_report()
    assert report.total_inspections == 20
    assert report.distinct_forms_inspected == 20
    assert report.forms_reviewed == 0
    assert report.is_gate_ready is False

    # 2. Human reviews all 20 records with 0 wrong sensitive answers
    for rec in records:
        orchestrator.record_human_review(
            record_id=rec.id,
            review_request=PilotReviewRequest(
                status=PilotReviewStatus.APPROVED,
                reviewer_id="lead_reviewer",
                notes="Accurate mapping verified against profile",
                incorrect_mappings_count=0,
                wrong_sensitive_count=0,
            ),
        )

    # Reviewed report: 20/20 reviewed, 100% accuracy -> Gate READY
    report2 = orchestrator.generate_quality_report()
    assert report2.forms_reviewed == 20
    assert report2.forms_pending_review == 0
    assert report2.reviewed_field_accuracy == 100.0
    assert report2.total_wrong_sensitive_answers == 0
    assert report2.is_gate_ready is True
