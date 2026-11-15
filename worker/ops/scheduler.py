"""Run Scheduler and Execution Concurrency Lock (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12, Appendix B)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
import logging
import random
import threading
from typing import Any, Callable, Coroutine, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SchedulerConfig(BaseModel):
    ist_active_start: int = Field(default=9, ge=0, le=23)
    ist_active_end: int = Field(default=23, ge=1, le=24)
    min_jitter_seconds: float = Field(default=1.0, ge=0.0)
    max_jitter_seconds: float = Field(default=5.0, ge=0.0)
    max_safe_retries: int = Field(default=2, ge=0, le=5)


class RunLockAcquisitionError(Exception):
    """Raised when an application run cannot be scheduled due to another run in progress."""


class SchedulerWindowError(Exception):
    """Raised when a run is attempted outside configured IST active hours."""


class RunScheduler:
    """Coordinates execution timing, single-run locks, jitter, and active hour enforcement."""

    def __init__(self, config: Optional[SchedulerConfig] = None) -> None:
        self.config = config or SchedulerConfig()
        self._single_run_lock = asyncio.Lock()
        self._is_running = False
        self._last_run_timestamp: Optional[datetime] = None
        self._catch_up_needed = False

    def is_within_active_hours(self, current_time: Optional[datetime] = None) -> bool:
        """Check whether current time falls within IST active window (09:00 - 23:00)."""
        now = current_time or datetime.now(timezone.utc)
        ist_offset = timedelta(hours=5, minutes=30)
        ist_time = now + ist_offset
        return self.config.ist_active_start <= ist_time.hour < self.config.ist_active_end

    async def apply_jitter(self) -> float:
        """Apply random jitter delay between execution steps to prevent thundering herds."""
        delay = random.uniform(self.config.min_jitter_seconds, self.config.max_jitter_seconds)
        await asyncio.sleep(delay)
        return delay

    async def execute_locked_run(
        self,
        run_name: str,
        coro_fn: Callable[[], Coroutine[Any, Any, Any]],
        enforce_active_hours: bool = True,
    ) -> Any:
        """Execute a job or discovery task inside a non-overlapping single-run lock.

        Guarantees:
        - Prevents overlapping application runs.
        - Enforces IST active hours if requested.
        - Records run timestamps.
        - Never automatically retries UNCERTAIN or SUBMITTING states.
        """
        if enforce_active_hours and not self.is_within_active_hours():
            raise SchedulerWindowError(
                f"Execution '{run_name}' rejected: outside IST active hours ({self.config.ist_active_start}:00-{self.config.ist_active_end}:00)."
            )

        if self._single_run_lock.locked():
            raise RunLockAcquisitionError(
                f"Cannot start '{run_name}': another run is already in progress (single-run lock active)."
            )

        async with self._single_run_lock:
            logger.info("Acquired single-run lock for '%s'", run_name)
            self._is_running = True
            try:
                result = await coro_fn()
                self._last_run_timestamp = datetime.now(timezone.utc)
                self._catch_up_needed = False
                return result
            finally:
                self._is_running = False
                logger.info("Released single-run lock for '%s'", run_name)

    def mark_machine_wake(self, sleep_duration_hours: float) -> None:
        """Flag that machine resumed from sleep, indicating catch-up discovery may be needed."""
        if sleep_duration_hours >= 1.0:
            self._catch_up_needed = True
            logger.info("Machine resumed from sleep (%sh); catch-up discovery flagged", sleep_duration_hours)

    def is_catch_up_needed(self) -> bool:
        return self._catch_up_needed
