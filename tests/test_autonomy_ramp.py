"""Tests for Provider Autonomy Control and Capacity Ramp Foundation (Phase 1.6).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12, Appendix B)
- docs/BUILD_RULES.md
"""

import pytest

from worker.application.models import AutonomyLevel
from worker.ops.autonomy import (
    AutonomyController,
    CapacityStage,
)


def test_autonomy_starts_at_l0_for_all_providers():
    controller = AutonomyController()
    assert controller.get_level("greenhouse") == AutonomyLevel.L0
    assert controller.get_level("lever") == AutonomyLevel.L0
    assert controller.get_level("naukri") == AutonomyLevel.L0


def test_owner_explicit_autonomy_update():
    controller = AutonomyController()
    controller.set_level_by_owner("greenhouse", AutonomyLevel.L1, actor="owner")
    assert controller.get_level("greenhouse") == AutonomyLevel.L1


def test_autonomy_promotion_criteria_evaluation_insufficient():
    controller = AutonomyController()

    # Only 15 applications (need 30), 96% accuracy (need 98%)
    report = controller.evaluate_eligibility(
        provider="naukri",
        total_apps_at_level=15,
        reviewed_accuracy=96.0,
        wrong_sensitive_count=0,
        duplicate_count=0,
    )
    assert report.eligible_for_next_level is False
    assert report.target_level == AutonomyLevel.L1
    assert len(report.missing_requirements) == 2
    assert report.can_auto_promote is False


def test_autonomy_promotion_criteria_evaluation_blocking_violations():
    controller = AutonomyController()

    # Has wrong sensitive answer and duplicate
    report = controller.evaluate_eligibility(
        provider="lever",
        total_apps_at_level=35,
        reviewed_accuracy=99.0,
        wrong_sensitive_count=1,
        duplicate_count=2,
    )
    assert report.eligible_for_next_level is False
    assert len(report.blocking_conditions) == 2


def test_autonomy_promotion_criteria_evaluation_eligible():
    controller = AutonomyController()

    report = controller.evaluate_eligibility(
        provider="greenhouse",
        total_apps_at_level=32,
        reviewed_accuracy=98.5,
        wrong_sensitive_count=0,
        duplicate_count=0,
    )
    assert report.eligible_for_next_level is True
    assert report.target_level == AutonomyLevel.L1
    # Note: Even when eligible, can_auto_promote is strictly False (owner approval required)
    assert report.can_auto_promote is False


def test_automatic_demotion_on_safety_violation():
    controller = AutonomyController()
    # Assume owner had previously authorized L2
    controller.set_level_by_owner("greenhouse", AutonomyLevel.L2, actor="owner")
    assert controller.get_level("greenhouse") == AutonomyLevel.L2

    # Demote due to policy violation
    new_level = controller.trigger_automatic_demotion("greenhouse", reason="Policy violation detected on SSN field")
    assert new_level == AutonomyLevel.L1
    assert controller.get_level("greenhouse") == AutonomyLevel.L1


def test_capacity_stage_evaluation_s0_to_s1():
    controller = AutonomyController()

    # Incomplete S0
    rep_inc = controller.evaluate_capacity_stage(
        current_stage=CapacityStage.S0,
        completed_dry_runs=12,
        approved_apps_total=0,
        accuracy_percent=95.0,
        policy_violations_count=0,
        duplicates_count=0,
    )
    assert rep_inc.is_eligible_for_advance is False
    assert rep_inc.active_daily_cap == 2  # Locked at 2

    # Complete S0
    rep_ready = controller.evaluate_capacity_stage(
        current_stage=CapacityStage.S0,
        completed_dry_runs=25,
        approved_apps_total=0,
        accuracy_percent=98.5,
        policy_violations_count=0,
        duplicates_count=0,
    )
    assert rep_ready.is_eligible_for_advance is True
    assert rep_ready.target_stage == CapacityStage.S1
    assert rep_ready.active_daily_cap == 2  # Never auto-increased
