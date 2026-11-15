"""Tests for Run Scheduler, Concurrency Lock, and Heartbeat (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12, Appendix B)
- docs/BUILD_RULES.md
"""

import asyncio
from datetime import datetime, timezone, timedelta
import pytest

from worker.ops.heartbeat import HeartbeatManager, HeartbeatStatus
from worker.ops.scheduler import (
    RunLockAcquisitionError,
    RunScheduler,
    SchedulerConfig,
    SchedulerWindowError,
)


@pytest.mark.asyncio
async def test_scheduler_single_run_lock_prevents_overlapping():
    scheduler = RunScheduler(SchedulerConfig())

    async def long_running_task():
        await asyncio.sleep(0.1)
        return "done"

    # Start first task
    task1 = asyncio.create_task(
        scheduler.execute_locked_run("run-1", long_running_task, enforce_active_hours=False)
    )
    await asyncio.sleep(0.01)

    # Attempt to start overlapping task
    with pytest.raises(RunLockAcquisitionError, match="single-run lock active"):
        await scheduler.execute_locked_run("run-2", long_running_task, enforce_active_hours=False)

    res = await task1
    assert res == "done"

    # Subsequent task after release succeeds
    res2 = await scheduler.execute_locked_run("run-3", long_running_task, enforce_active_hours=False)
    assert res2 == "done"


@pytest.mark.asyncio
async def test_scheduler_jitter():
    config = SchedulerConfig(min_jitter_seconds=0.02, max_jitter_seconds=0.05)
    scheduler = RunScheduler(config)

    delay = await scheduler.apply_jitter()
    assert 0.02 <= delay <= 0.05


def test_scheduler_ist_active_hours_check():
    config = SchedulerConfig(ist_active_start=9, ist_active_end=23)
    scheduler = RunScheduler(config)

    # UTC 04:00 is IST 09:30 (inside 09:00 - 23:00)
    utc_morning = datetime(2026, 11, 15, 4, 0, 0, tzinfo=timezone.utc)
    assert scheduler.is_within_active_hours(utc_morning) is True

    # UTC 01:00 is IST 06:30 (outside active window)
    utc_early = datetime(2026, 11, 15, 1, 0, 0, tzinfo=timezone.utc)
    assert scheduler.is_within_active_hours(utc_early) is False


def test_scheduler_catch_up_flag():
    scheduler = RunScheduler()
    assert scheduler.is_catch_up_needed() is False

    scheduler.mark_machine_wake(sleep_duration_hours=2.5)
    assert scheduler.is_catch_up_needed() is True


def test_heartbeat_healthy_pulse_and_run():
    mgr = HeartbeatManager(worker_id="test-worker")
    state = mgr.pulse(active_job_id="job-123")
    assert state.status == HeartbeatStatus.HEALTHY
    assert state.active_job_id == "job-123"

    state_done = mgr.record_run_completed()
    assert state_done.total_runs_completed == 1
    assert state_done.active_job_id is None


def test_heartbeat_dead_man_alert_during_ist_active_hours():
    mgr = HeartbeatManager(
        worker_id="test-worker",
        stale_threshold_hours=2.0,
        ist_active_start=9,
        ist_active_end=23,
    )
    # Heartbeat was at UTC 04:00 (IST 09:30)
    start_time = datetime(2026, 11, 15, 4, 0, 0, tzinfo=timezone.utc)
    mgr._state = mgr._state.model_copy(update={"last_heartbeat": start_time})

    # Evaluated at UTC 07:00 (IST 12:30, 3 hours later)
    check_time = datetime(2026, 11, 15, 7, 0, 0, tzinfo=timezone.utc)
    state = mgr.check_health(current_time=check_time)
    assert state.status == HeartbeatStatus.DEAD
