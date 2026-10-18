"""Kill switch abstraction and state implementations enforcing fail-closed safety."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol, Union

from pydantic import BaseModel, Field

from worker.core.exceptions import InvalidSafetyStateError, KillSwitchActiveError


class KillSwitchRecord(BaseModel):
    """Schema for persisted kill switch state."""

    automation_enabled: bool = Field(
        ...,
        description="True if automation is permitted; False if kill switch is engaged.",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason why the kill switch was engaged or updated.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the last state update.",
    )
    updated_by: str = Field(
        default="system",
        description="Actor or component responsible for the state update.",
    )


class KillSwitch(Protocol):
    """Abstract interface defining the kill switch contract."""

    def is_automation_enabled(self) -> bool:
        """Return True if automation is enabled, False if blocked."""
        ...

    def verify_automation_allowed(self) -> None:
        """Verify automation is permitted; raise typed error if blocked."""
        ...

    def trip(self, reason: str, updated_by: str = "system") -> None:
        """Engage the kill switch, immediately halting automation."""
        ...

    def reset(self, updated_by: str = "system") -> None:
        """Disengage the kill switch, re-enabling automation."""
        ...


class InMemoryKillSwitch:
    """In-memory kill switch implementation for isolated automated testing.

    LIMITATION: This implementation stores state purely in memory and does
    NOT persist across process restarts. It must only be used in test suites.
    """

    def __init__(self, initial_enabled: bool = True) -> None:
        self._enabled = initial_enabled
        self._reason: Optional[str] = None
        self._updated_by: str = "init"
        self._updated_at: datetime = datetime.now(timezone.utc)

    def is_automation_enabled(self) -> bool:
        return self._enabled

    def verify_automation_allowed(self) -> None:
        if not self._enabled:
            raise KillSwitchActiveError(
                f"Automation is blocked by kill switch: {self._reason or 'Kill switch active'}"
            )

    def trip(self, reason: str, updated_by: str = "system") -> None:
        self._enabled = False
        self._reason = reason
        self._updated_by = updated_by
        self._updated_at = datetime.now(timezone.utc)

    def reset(self, updated_by: str = "system") -> None:
        self._enabled = True
        self._reason = None
        self._updated_by = updated_by
        self._updated_at = datetime.now(timezone.utc)


class FileKillSwitch:
    """Local file-persisted kill switch for worker process restarts.

    SAFETY RULE: Defaults to fail-closed. If the state file is missing,
    corrupted, or unreadable, automation is strictly treated as disabled.
    """

    def __init__(self, file_path: Union[str, Path]) -> None:
        self.file_path = Path(file_path)

    def _read_record(self) -> KillSwitchRecord:
        """Read and validate the record from disk; fail-closed on any error."""
        if not self.file_path.exists():
            raise InvalidSafetyStateError(
                f"Kill switch state file missing at '{self.file_path}'. Failing closed."
            )

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            return KillSwitchRecord.model_validate(raw_data)
        except Exception as exc:
            raise InvalidSafetyStateError(
                f"Kill switch state file corrupted or unreadable at '{self.file_path}': {exc}. Failing closed."
            ) from exc

    def _write_record(self, record: KillSwitchRecord) -> None:
        """Persist state atomically."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.file_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(record.model_dump_json(indent=2))
        tmp_path.replace(self.file_path)

    def is_automation_enabled(self) -> bool:
        """Check whether automation is allowed; returns False if file is invalid."""
        try:
            record = self._read_record()
            return record.automation_enabled
        except InvalidSafetyStateError:
            return False

    def verify_automation_allowed(self) -> None:
        """Enforce automation check; raises typed error if tripped or state is invalid."""
        record = self._read_record()
        if not record.automation_enabled:
            raise KillSwitchActiveError(
                f"Automation is blocked by kill switch: {record.reason or 'Kill switch engaged'}"
            )

    def trip(self, reason: str, updated_by: str = "system") -> None:
        """Engage the kill switch on disk."""
        record = KillSwitchRecord(
            automation_enabled=False,
            reason=reason,
            updated_at=datetime.now(timezone.utc),
            updated_by=updated_by,
        )
        self._write_record(record)

    def reset(self, updated_by: str = "system") -> None:
        """Disengage the kill switch on disk, permitting automation."""
        record = KillSwitchRecord(
            automation_enabled=True,
            reason=None,
            updated_at=datetime.now(timezone.utc),
            updated_by=updated_by,
        )
        self._write_record(record)
