"""Unit tests for Phase 2.7: L1 Supervised Execution Preparation and Pre-Submission Simulation.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12, 13)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from uuid import uuid4

from worker.application.models import Application, ApplicationStatus, AutonomyLevel
from worker.application.supervised import (
    PreSubmissionSimulationReport,
    SupervisedExecutionSimulator,
)
from worker.core.caps import CapsConfig, CapsEnforcer, InMemoryApplicationLedger
from worker.core.exceptions import (
    KillSwitchActiveError,
    RealSubmitGateBlockedError,
)
from worker.core.kill_switch import InMemoryKillSwitch
from worker.core.safety import SafetyEngine
from worker.ops.autonomy import AutonomyController
from worker.ops.provider_health import ProviderHealthManager


@pytest.fixture
def mock_application() -> Application:
    return Application(
        id=uuid4(),
        user_id=uuid4(),
        job_id=uuid4(),
        platform="greenhouse",
        external_id="gh-sim-001",
        profile_version="v1.0-sim",
        autonomy_level=AutonomyLevel.L1,
        status=ApplicationStatus.READY,
        idempotency_key=f"idemp-{uuid4().hex[:12]}",
    )


@pytest.mark.asyncio
async def test_supervised_simulation_clean_pass(mock_application: Application):
    """Verify pre-submission simulation passes when all safety checks and fill plan fields are clean."""
    ks = InMemoryKillSwitch(initial_enabled=True)
    ledger = InMemoryApplicationLedger()
    caps = CapsEnforcer(config=CapsConfig(), ledger=ledger)
    safety = SafetyEngine(kill_switch=ks, caps_enforcer=caps, real_submit_gate_enabled=False)

    simulator = SupervisedExecutionSimulator(safety_engine=safety)

    fill_plan = {
        "fields": [
            {"name": "first_name", "value": "Jane", "required": True, "policy": "auto"},
            {"name": "email", "value": "jane@example.com", "required": True, "policy": "auto"},
            {"name": "salary", "value": 150000, "required": False, "policy": "always_ask", "is_sensitive": True},
        ]
    }

    report: PreSubmissionSimulationReport = await simulator.simulate_pre_submission(
        application=mock_application,
        company="Acme Corp",
        fill_plan=fill_plan,
        attempt_real_submit=False,
    )

    assert report.can_proceed_to_pre_submit is True
    assert report.safety_checks_passed is True
    assert len(report.blocking_reasons) == 0
    assert report.fill_plan_field_count == 3
    assert "salary" in report.sensitive_fields
    assert report.real_submit_gate_status == "LOCKED_DISABLED"


@pytest.mark.asyncio
async def test_supervised_simulation_strictly_rejects_real_submit(mock_application: Application):
    """Verify that any attempt to perform real submission raises RealSubmitGateBlockedError."""
    simulator = SupervisedExecutionSimulator()

    fill_plan = {"fields": []}
    with pytest.raises(RealSubmitGateBlockedError):
        await simulator.simulate_pre_submission(
            application=mock_application,
            company="Acme Corp",
            fill_plan=fill_plan,
            attempt_real_submit=True,
        )


@pytest.mark.asyncio
async def test_supervised_simulation_blocks_on_kill_switch(mock_application: Application):
    """Verify active kill switch causes simulation to report blocking reason."""
    ks = InMemoryKillSwitch(initial_enabled=False)  # automation disabled
    ledger = InMemoryApplicationLedger()
    caps = CapsEnforcer(config=CapsConfig(), ledger=ledger)
    safety = SafetyEngine(kill_switch=ks, caps_enforcer=caps, real_submit_gate_enabled=False)

    simulator = SupervisedExecutionSimulator(safety_engine=safety)

    fill_plan = {"fields": []}
    report = await simulator.simulate_pre_submission(
        application=mock_application,
        company="Acme Corp",
        fill_plan=fill_plan,
        attempt_real_submit=False,
    )

    assert report.can_proceed_to_pre_submit is False
    assert any("Kill switch active" in b for b in report.blocking_reasons)


@pytest.mark.asyncio
async def test_supervised_simulation_detects_unresolved_required_and_expired_fields(
    mock_application: Application,
):
    """Verify unresolved required fields and expired answers block simulation."""
    simulator = SupervisedExecutionSimulator()

    fill_plan = {
        "fields": [
            {"name": "portfolio_url", "value": None, "required": True, "policy": "auto"},
            {"name": "salary_requirement", "value": 120000, "required": False, "is_expired": True},
        ]
    }

    report = await simulator.simulate_pre_submission(
        application=mock_application,
        company="Acme Corp",
        fill_plan=fill_plan,
    )

    assert report.can_proceed_to_pre_submit is False
    assert any("unresolved" in b for b in report.blocking_reasons)
    assert any("expired" in b for b in report.blocking_reasons)


def test_autonomy_eligibility_and_ramp_rules():
    """Verify L1 eligibility criteria, LinkedIn restriction, and zero auto-promotion."""
    controller = AutonomyController()

    # Greenhouse at L0 evaluating for L1
    rep = controller.evaluate_eligibility(
        provider="greenhouse",
        total_apps_at_level=35,
        reviewed_accuracy=98.5,
        wrong_sensitive_count=0,
        duplicate_count=0,
    )
    assert rep.eligible_for_next_level is True
    assert rep.target_level == AutonomyLevel.L1
    assert rep.can_auto_promote is False  # Must require human authorization

    # LinkedIn capped at L1; promotion to L2 is blocked
    controller.set_level_by_owner("linkedin", AutonomyLevel.L1)
    rep_li = controller.evaluate_eligibility(
        provider="linkedin",
        total_apps_at_level=50,
        reviewed_accuracy=99.0,
        wrong_sensitive_count=0,
        duplicate_count=0,
    )
    assert rep_li.eligible_for_next_level is False
    assert any("LinkedIn is restricted" in b for b in rep_li.blocking_conditions)
