"""Tests for Provider Health Manager and Canary Drift Detection (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12)
- docs/BUILD_RULES.md
"""

import pytest

from worker.ops.canary import ProviderCanaryRunner
from worker.ops.provider_health import ProviderHealthManager, ProviderStatus


def test_three_consecutive_failures_trigger_auto_pause():
    paused_notifications = []

    def on_pause(prov, reason, count):
        paused_notifications.append((prov, reason, count))

    mgr = ProviderHealthManager(max_consecutive_failures=3, on_auto_pause_callback=on_pause)

    # 1st failure -> DEGRADED
    mgr.record_failure("greenhouse", "selector", "Missing first_name input")
    assert mgr.is_provider_available("greenhouse") is True

    # 2nd failure -> DEGRADED
    mgr.record_failure("greenhouse", "timeout", "Navigation timed out after 30s")
    assert mgr.is_provider_available("greenhouse") is True

    # 3rd failure -> PAUSED
    state = mgr.record_failure("greenhouse", "crash", "Chromium crashed")
    assert state.status == ProviderStatus.PAUSED
    assert mgr.is_provider_available("greenhouse") is False
    assert len(paused_notifications) == 1
    assert paused_notifications[0][0] == "greenhouse"
    assert paused_notifications[0][2] == 3


def test_provider_isolation():
    mgr = ProviderHealthManager(max_consecutive_failures=3)

    # Fail greenhouse 3 times
    for _ in range(3):
        mgr.record_failure("greenhouse", "crash", "Crash")

    assert mgr.is_provider_available("greenhouse") is False
    # Lever should remain healthy and available!
    assert mgr.is_provider_available("lever") is True


def test_manual_resume_provider():
    mgr = ProviderHealthManager(max_consecutive_failures=3)
    for _ in range(3):
        mgr.record_failure("greenhouse", "crash", "Crash")
    assert mgr.is_provider_available("greenhouse") is False

    resumed = mgr.resume_provider("greenhouse")
    assert resumed.status == ProviderStatus.HEALTHY
    assert resumed.consecutive_failures == 0
    assert mgr.is_provider_available("greenhouse") is True


@pytest.mark.asyncio
async def test_canary_greenhouse_and_lever_success():
    health_mgr = ProviderHealthManager()
    canary = ProviderCanaryRunner(health_mgr=health_mgr)

    gh_res = await canary.run_canary("greenhouse")
    assert gh_res.is_available is True
    assert gh_res.safe_to_operate is True
    assert gh_res.total_fields_found >= 8
    assert gh_res.structural_drift_detected is False

    lever_res = await canary.run_canary("lever")
    assert lever_res.is_available is True
    assert lever_res.safe_to_operate is True
    assert lever_res.total_fields_found >= 8
    assert lever_res.structural_drift_detected is False


@pytest.mark.asyncio
async def test_canary_unknown_provider_fails_safely():
    health_mgr = ProviderHealthManager()
    canary = ProviderCanaryRunner(health_mgr=health_mgr)

    res = await canary.run_canary("nonexistent_provider")
    assert res.is_available is False
    assert res.safe_to_operate is False
    assert res.structural_drift_detected is True
