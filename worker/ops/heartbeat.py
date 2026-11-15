"""Worker Heartbeat and Dead-Man Monitoring (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from enum import Enum
import logging
import threading
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class HeartbeatStatus(str, Enum):
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    DEAD = "DEAD"


class HeartbeatState(BaseModel):
    worker_id: str
    status: HeartbeatStatus = HeartbeatStatus.HEALTHY
    last_heartbeat: datetime
    last_successful_run: Optional[datetime] = None
    active_job_id: Optional[str] = None
    total_runs_completed: int = 0


class HeartbeatManager:
    """Manages worker process heartbeat signals and dead-man alert detection."""

    def __init__(
        self,
        worker_id: str = "worker-primary",
        stale_threshold_hours: float = 2.0,
        ist_active_start: int = 9,
        ist_active_end: int = 23,
    ) -> None:
        self.worker_id = worker_id
        self.stale_threshold = timedelta(hours=stale_threshold_hours)
        self.ist_active_start = ist_active_start
        self.ist_active_end = ist_active_end
        self._lock = threading.Lock()
        now = datetime.now(timezone.utc)
        self._state = HeartbeatState(worker_id=worker_id, last_heartbeat=now)

    def pulse(self, active_job_id: Optional[str] = None) -> HeartbeatState:
        """Worker sends a heartbeat pulse."""
        with self._lock:
            now = datetime.now(timezone.utc)
            self._state = self._state.model_copy(
                update={
                    "last_heartbeat": now,
                    "active_job_id": active_job_id,
                    "status": HeartbeatStatus.HEALTHY,
                }
            )
            return self._state.model_copy()

    def record_run_completed(self) -> HeartbeatState:
        with self._lock:
            now = datetime.now(timezone.utc)
            self._state = self._state.model_copy(
                update={
                    "last_heartbeat": now,
                    "last_successful_run": now,
                    "active_job_id": None,
                    "total_runs_completed": self._state.total_runs_completed + 1,
                    "status": HeartbeatStatus.HEALTHY,
                }
            )
            return self._state.model_copy()

    def check_health(self, current_time: Optional[datetime] = None) -> HeartbeatState:
        """Inspect health and evaluate dead-man condition against IST active hours."""
        now = current_time or datetime.now(timezone.utc)
        with self._lock:
            age = now - self._state.last_heartbeat
            is_active_window = self._is_ist_active_hour(now)

            if age > self.stale_threshold:
                if is_active_window:
                    new_status = HeartbeatStatus.DEAD
                    logger.critical(
                        "DEAD-MAN ALERT: Worker %s heartbeat is %s hours stale during IST active hours (%02d:00-%02d:00)",
                        self.worker_id,
                        age.total_seconds() / 3600.0,
                        self.ist_active_start,
                        self.ist_active_end,
                    )
                else:
                    new_status = HeartbeatStatus.STALE
            else:
                new_status = HeartbeatStatus.HEALTHY

            self._state = self._state.model_copy(update={"status": new_status})
            return self._state.model_copy()

    def _is_ist_active_hour(self, utc_time: datetime) -> bool:
        """Convert UTC to IST (UTC+5:30) and check if within active window."""
        ist_offset = timedelta(hours=5, minutes=30)
        ist_time = utc_time + ist_offset
        return self.ist_active_start <= ist_time.hour < self.ist_active_end
