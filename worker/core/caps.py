"""Application rate caps enforcement and accounting ledger."""

import json
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, List, Optional, Protocol, Union

from pydantic import BaseModel, Field

from services.api.config import CapsConfig
from worker.core.exceptions import (
    CompanyCooldownExceededError,
    CompanyDailyCapExceededError,
    GlobalDailyCapExceededError,
    InvalidSafetyStateError,
    ProviderDailyCapExceededError,
)


class ApplicationRecord(BaseModel):
    """Immutable event record of an application attempt for rate cap accounting."""

    id: str = Field(..., description="Unique application or event ID")
    company: str = Field(..., description="Normalized target company name")
    provider: str = Field(..., description="Target job board provider (e.g. greenhouse, lever)")
    applied_at: datetime = Field(..., description="UTC timestamp of the application")
    status: str = Field(default="SUBMITTED", description="Status (e.g. SUBMITTED, DRY_RUN)")


class ApplicationLedger(Protocol):
    """Protocol for recording and querying application history for cap checks."""

    def record_submission(self, record: ApplicationRecord) -> None:
        """Persist an application record."""
        ...

    def count_daily_applications(self, target_date: date, provider: Optional[str] = None) -> int:
        """Count total applications on a specific calendar date (UTC)."""
        ...

    def count_company_applications_since(self, company: str, since: datetime) -> int:
        """Count applications to a specific company since a given timestamp."""
        ...


class InMemoryApplicationLedger:
    """In-memory application ledger for fast, isolated unit testing.

    LIMITATION: Stored purely in process memory; records do NOT persist
    across process restarts.
    """

    def __init__(self) -> None:
        self._records: List[ApplicationRecord] = []

    def record_submission(self, record: ApplicationRecord) -> None:
        self._records.append(record)

    def count_daily_applications(self, target_date: date, provider: Optional[str] = None) -> int:
        count = 0
        for r in self._records:
            record_date = r.applied_at.astimezone(timezone.utc).date()
            if record_date == target_date:
                if provider is None or r.provider.lower() == provider.lower():
                    count += 1
        return count

    def count_company_applications_since(self, company: str, since: datetime) -> int:
        norm_company = company.strip().lower()
        count = 0
        for r in self._records:
            if r.company.strip().lower() == norm_company and r.applied_at >= since:
                count += 1
        return count


class FileApplicationLedger:
    """Durable append-only JSON Lines ledger for application history.

    Survives process restarts to prevent daily and cooldown cap resets.

    CONCURRENCY & PERSISTENCE GUARANTEES:
    - Thread-safe within a single process via an internal threading.Lock.
    - Readers and writers synchronize under the lock, preventing readers from
      observing partially written lines or interleaved writes within the process.
    - LIMITATION: Does NOT provide cross-process OS file locks across separate
      OS processes. The Job Agent architecture specifies a single dedicated
      local worker process per host.
    """

    def __init__(self, file_path: Union[str, Path]) -> None:
        self.file_path = Path(file_path)
        self._lock = threading.Lock()

    def record_submission(self, record: ApplicationRecord) -> None:
        with self._lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(record.model_dump_json() + "\n")

    def _read_all_records(self) -> List[ApplicationRecord]:
        with self._lock:
            if not self.file_path.exists():
                return []

            records = []
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    clean = line.strip()
                    if not clean:
                        continue
                    try:
                        records.append(ApplicationRecord.model_validate_json(clean))
                    except Exception as exc:
                        raise InvalidSafetyStateError(
                            f"Corrupted ledger entry at line {line_no} in '{self.file_path}': {exc}"
                        ) from exc
            return records

    def count_daily_applications(self, target_date: date, provider: Optional[str] = None) -> int:
        records = self._read_all_records()
        count = 0
        for r in records:
            record_date = r.applied_at.astimezone(timezone.utc).date()
            if record_date == target_date:
                if provider is None or r.provider.lower() == provider.lower():
                    count += 1
        return count

    def count_company_applications_since(self, company: str, since: datetime) -> int:
        records = self._read_all_records()
        norm_company = company.strip().lower()
        count = 0
        for r in records:
            if r.company.strip().lower() == norm_company and r.applied_at >= since:
                count += 1
        return count


class CapsEnforcer:
    """Enforces daily and per-company application limits defined in CapsConfig."""

    def __init__(
        self,
        config: CapsConfig,
        ledger: ApplicationLedger,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        if config is None:
            raise InvalidSafetyStateError("CapsConfig is required for cap enforcement; failing closed.")
        self.config = config
        self.ledger = ledger
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def check_caps(
        self,
        company: str,
        provider: str,
        now: Optional[datetime] = None,
    ) -> None:
        """Verify that an application to (company, provider) is within all limits.

        Raises:
            GlobalDailyCapExceededError: When global daily applications ceiling is reached.
            ProviderDailyCapExceededError: When provider daily ceiling is reached.
            CompanyDailyCapExceededError: When 24-hour ceiling for this company is reached.
            CompanyCooldownExceededError: When 30-day cooldown ceiling for this company is reached.
        """
        current_time = now or self.clock()
        today = current_time.astimezone(timezone.utc).date()

        # 1. Global daily cap
        global_count = self.ledger.count_daily_applications(today)
        if global_count >= self.config.global_per_day:
            raise GlobalDailyCapExceededError(
                f"Global daily cap reached: {global_count}/{self.config.global_per_day} applications submitted on {today}"
            )

        # 2. Provider daily cap
        norm_provider = provider.strip().lower()
        provider_limit = self.config.per_provider_per_day.get(norm_provider)
        if provider_limit is not None:
            provider_count = self.ledger.count_daily_applications(today, provider=norm_provider)
            if provider_count >= provider_limit:
                raise ProviderDailyCapExceededError(
                    f"Provider daily cap reached for '{provider}': {provider_count}/{provider_limit} on {today}"
                )

        # 3. Company daily cap (last 24 hours)
        last_24h = current_time - timedelta(days=1)
        company_24h_count = self.ledger.count_company_applications_since(company, since=last_24h)
        if company_24h_count >= self.config.per_company_per_day:
            raise CompanyDailyCapExceededError(
                f"Company daily limit reached for '{company}': {company_24h_count}/{self.config.per_company_per_day} in last 24 hours"
            )

        # 4. Company 30-day cooldown
        last_30d = current_time - timedelta(days=30)
        company_30d_count = self.ledger.count_company_applications_since(company, since=last_30d)
        if company_30d_count >= self.config.per_company_per_30d:
            raise CompanyCooldownExceededError(
                f"Company cooldown in effect for '{company}': {company_30d_count}/{self.config.per_company_per_30d} application(s) within 30 days"
            )
