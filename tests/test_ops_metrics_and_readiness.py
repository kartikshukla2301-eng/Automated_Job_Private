"""Tests for Operational Metrics and Real-Submit Readiness Evaluator (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12)
- docs/BUILD_RULES.md
"""

from uuid import uuid4
import pytest

from worker.application.models import Application, ApplicationStatus
from worker.application.repository import (
    InMemoryApplicationEventRepository,
    InMemoryApplicationRepository,
)
from worker.ops.metrics import MetricsAggregator
from worker.ops.provider_health import ProviderHealthManager
from worker.ops.readiness import CriterionStatus, RealSubmitReadinessEvaluator


@pytest.mark.asyncio
async def test_metrics_aggregator_derived_truthfully():
    app_repo = InMemoryApplicationRepository()
    event_repo = InMemoryApplicationEventRepository()
    health_mgr = ProviderHealthManager()
    user_id = uuid4()

    # Create applications in various statuses
    app1 = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-m1",
        profile_version="v1.0",
        status=ApplicationStatus.AWAITING_APPROVAL,
        idempotency_key="key-m1",
    )
    app2 = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="lever",
        external_id="ext-m2",
        profile_version="v1.0",
        status=ApplicationStatus.DRY_RUN_DONE,
        idempotency_key="key-m2",
    )
    app3 = Application(
        id=uuid4(),
        user_id=user_id,
        job_id=uuid4(),
        platform="greenhouse",
        external_id="ext-m3",
        profile_version="v1.0",
        status=ApplicationStatus.NEEDS_USER_INPUT,
        idempotency_key="key-m3",
    )
    await app_repo.create(app1)
    await app_repo.create(app2)
    await app_repo.create(app3)

    aggregator = MetricsAggregator(
        application_repo=app_repo,
        event_repo=event_repo,
        job_repo=None,
        health_mgr=health_mgr,
    )

    metrics = await aggregator.get_user_metrics(user_id)
    assert metrics.applications_total == 3
    assert metrics.applications_awaiting_approval == 1
    assert metrics.applications_dry_run_done == 1
    assert metrics.applications_needs_user_input == 1
    assert metrics.applications_applied == 0
    assert metrics.applications_failed == 0


def test_readiness_evaluator_unverified_criteria_and_hardcoded_false():
    evaluator = RealSubmitReadinessEvaluator(
        kill_switch_tested=True,
        caps_enforced=True,
        policy_golden_tests_green=True,
        evidence_capture_working=True,
        crash_recovery_verified=True,
        telegram_alerts_verified=False,  # Unverified
        reviewed_real_forms_count=5,     # Less than 20
        reviewed_field_accuracy=95.0,    # Less than 98%
    )

    report = evaluator.evaluate()
    assert report.real_submit_gate_enabled is False  # MUST BE HARDCODED FALSE
    assert report.overall_status == CriterionStatus.NOT_READY

    # Check specific criterion details
    crit_forms = next(c for c in report.criteria if c.id == "G-04")
    assert crit_forms.status == CriterionStatus.NOT_READY
    assert "5/20" in crit_forms.missing_reason

    crit_acc = next(c for c in report.criteria if c.id == "G-05")
    assert crit_acc.status == CriterionStatus.NOT_READY

    crit_tg = next(c for c in report.criteria if c.id == "G-08")
    assert crit_tg.status == CriterionStatus.UNVERIFIED


def test_readiness_evaluator_all_satisfied_still_keeps_gate_false():
    evaluator = RealSubmitReadinessEvaluator(
        kill_switch_tested=True,
        caps_enforced=True,
        policy_golden_tests_green=True,
        evidence_capture_working=True,
        crash_recovery_verified=True,
        telegram_alerts_verified=True,
        reviewed_real_forms_count=25,
        reviewed_field_accuracy=99.2,
        zero_wrong_sensitive_answers=True,
    )

    report = evaluator.evaluate()
    # Even if all criteria are READY, real_submit_gate_enabled MUST remain False
    assert report.real_submit_gate_enabled is False
    assert report.overall_status == CriterionStatus.READY
