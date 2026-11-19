"""Weekly Automatic Backup Scheduling for Answer Bank & Profile Snapshot (Phase 4.1, OI-8).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Part I.4, Optional Improvement OI-8:
  "Weekly automatic export/backup of the Answer Bank and profile snapshot.")
- docs/BUILD_RULES.md

Scope: this module only decides *when* a weekly backup is due and persists that
decision; it delegates the actual bundling/checksum work to the existing
`BackupManager` (worker/ops/backup.py, Phase 2.6) so there is a single, already-tested
backup format. It intentionally never includes `applications`/`events` in the
scheduled export — OI-8 scopes this to the Answer Bank and profile snapshot only.
The broader, operator-triggered backup (including applications/events) continues to
go through `BackupManager.create_backup()` directly elsewhere.

This intentionally does not add the `apscheduler` package: the rest of this worker
(`worker/ops/scheduler.py`) already implements scheduling as a lightweight, testable
"is it due" check plus a persisted timestamp rather than a cron daemon, and this
module follows the same pattern for consistency and to avoid a redundant dependency.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from worker.ops.backup import BackupBundle, BackupManager

logger = logging.getLogger("worker.ops.backup_schedule")

# worker/sessions/ is gitignored (see .gitignore: "worker/sessions/*"); reusing it
# keeps scheduled backups out of version control without inventing a new ignore rule.
DEFAULT_STATE_PATH = Path("worker/sessions/backups/weekly_backup_state.json")
DEFAULT_BACKUP_DIR = Path("worker/sessions/backups")


class WeeklyBackupState(BaseModel):
    """Persisted record of the most recent scheduled weekly backup."""

    model_config = ConfigDict(extra="forbid")

    last_backup_at: Optional[datetime] = None
    last_backup_id: Optional[str] = None
    total_backups_created: int = Field(default=0, ge=0)


class WeeklyBackupScheduler:
    """Decides when a weekly Answer Bank + profile snapshot export is due, and runs it.

    Thread-safe and fail-closed on load: a missing or corrupt state file is treated as
    "no backup has ever run", which only causes an extra (harmless) backup sooner —
    it never silently skips a backup that was actually due.
    """

    def __init__(
        self,
        state_path: Path = DEFAULT_STATE_PATH,
        backup_dir: Path = DEFAULT_BACKUP_DIR,
        interval_days: int = 7,
    ) -> None:
        if interval_days < 1:
            raise ValueError("interval_days must be at least 1")
        self.state_path = state_path
        self.backup_dir = backup_dir
        self.interval_days = interval_days
        self._lock = threading.Lock()
        self._state = self._load()

    def _load(self) -> WeeklyBackupState:
        if self.state_path.exists():
            try:
                return WeeklyBackupState.model_validate(
                    json.loads(self.state_path.read_text(encoding="utf-8"))
                )
            except Exception:
                logger.warning(
                    "Weekly backup state file unreadable/corrupt at %s; "
                    "treating as never backed up (fail closed toward re-backing up).",
                    self.state_path,
                )
        return WeeklyBackupState()

    def _save_locked(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(self._state.model_dump_json(indent=2), encoding="utf-8")

    def get_state(self) -> WeeklyBackupState:
        with self._lock:
            return self._state.model_copy()

    def is_due(self, now: Optional[datetime] = None) -> bool:
        """True if no backup has ever run, or the configured interval has elapsed."""
        current = now or datetime.now(timezone.utc)
        with self._lock:
            if self._state.last_backup_at is None:
                return True
            return current - self._state.last_backup_at >= timedelta(days=self.interval_days)

    def run_if_due(
        self,
        answer_bank_entries: Optional[List[Any]] = None,
        profile_snapshots: Optional[List[Any]] = None,
        now: Optional[datetime] = None,
    ) -> Optional[BackupBundle]:
        """Create and persist a scoped Answer Bank + profile snapshot backup if due.

        Returns the created `BackupBundle`, or `None` if a backup was not due yet.
        Scope is intentionally limited to Answer Bank and profile snapshots per OI-8;
        `applications`/`events` are never accepted or included here.
        """
        current = now or datetime.now(timezone.utc)
        if not self.is_due(current):
            return None

        timestamp_slug = current.strftime("%Y%m%dT%H%M%SZ")
        output_path = self.backup_dir / f"weekly_backup_{timestamp_slug}.json"

        bundle = BackupManager.create_backup(
            answer_bank_entries=answer_bank_entries,
            profile_snapshots=profile_snapshots,
            output_path=output_path,
        )

        with self._lock:
            self._state = self._state.model_copy(
                update={
                    "last_backup_at": current,
                    "last_backup_id": bundle.metadata.backup_id,
                    "total_backups_created": self._state.total_backups_created + 1,
                }
            )
            self._save_locked()

        logger.info(
            "Weekly Answer Bank/profile snapshot backup created: id=%s path=%s",
            bundle.metadata.backup_id,
            output_path,
        )
        return bundle
