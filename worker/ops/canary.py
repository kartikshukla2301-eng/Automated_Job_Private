"""Provider Canary Testing and Form Drift Detection (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from worker.browser.page_inspector import PageInspector
from worker.ops.provider_health import ProviderHealthManager

logger = logging.getLogger(__name__)


class CanaryResult(BaseModel):
    provider: str
    target_fixture: str
    executed_at: datetime
    is_available: bool
    total_fields_found: int
    required_fields_count: int
    selector_failures_count: int
    structural_drift_detected: bool
    drift_details: List[str] = Field(default_factory=list)
    safe_to_operate: bool


class ProviderCanaryRunner:
    """Executes periodic canary inspections on approved local test fixtures or canaries.

    Rules:
    - Never submits forms.
    - Never enters candidate data or personal PII.
    - Compares current structure against expected baseline.
    - Pauses provider via ProviderHealthManager if canary fails catastrophically.
    """

    # Baselines for supported providers
    BASELINES = {
        "greenhouse": {
            "fixture": "fixtures/forms/greenhouse_job.html",
            "min_fields": 8,
            "min_required": 4,
            "required_field_ids": ["first_name", "last_name", "email", "phone"],
        },
        "lever": {
            "fixture": "fixtures/forms/lever_job.html",
            "min_fields": 8,
            "min_required": 4,
            "required_field_ids": ["name", "email", "phone", "org"],
        },
    }

    def __init__(
        self,
        health_mgr: Optional[ProviderHealthManager] = None,
        page_inspector: Optional[PageInspector] = None,
    ) -> None:
        self.health_mgr = health_mgr
        self.inspector = page_inspector or PageInspector()
        self.history: List[CanaryResult] = []

    async def run_canary(self, provider: str) -> CanaryResult:
        """Run canary on the provider's approved fixture and evaluate drift."""
        prov = provider.lower()
        baseline = self.BASELINES.get(prov)
        now = datetime.now(timezone.utc)

        if not baseline:
            result = CanaryResult(
                provider=prov,
                target_fixture="unknown",
                executed_at=now,
                is_available=False,
                total_fields_found=0,
                required_fields_count=0,
                selector_failures_count=1,
                structural_drift_detected=True,
                drift_details=[f"No canary baseline defined for provider '{prov}'"],
                safe_to_operate=False,
            )
            self.history.append(result)
            return result

        fixture_path = Path(baseline["fixture"])
        if not fixture_path.exists():
            result = CanaryResult(
                provider=prov,
                target_fixture=str(fixture_path),
                executed_at=now,
                is_available=False,
                total_fields_found=0,
                required_fields_count=0,
                selector_failures_count=1,
                structural_drift_detected=True,
                drift_details=[f"Canary fixture missing: {fixture_path}"],
                safe_to_operate=False,
            )
            self._handle_canary_failure(prov, "Canary fixture missing")
            self.history.append(result)
            return result

        try:
            # Inspect form using offline parser (guarantees zero external network or data submission)
            html = fixture_path.read_text(encoding="utf-8")
            fields = self.inspector.inspect_html(html)

            total_found = len(fields)
            required_fields = [f for f in fields if f.required]
            required_count = len(required_fields)

            found_ids = {f.field_id for f in fields}
            missing_expected = [
                req_id for req_id in baseline["required_field_ids"] if req_id not in found_ids
            ]

            drift_details: List[str] = []
            if total_found < baseline["min_fields"]:
                drift_details.append(
                    f"Total fields dropped from expected >={baseline['min_fields']} to {total_found}"
                )
            if missing_expected:
                drift_details.append(f"Missing mandatory baseline fields: {', '.join(missing_expected)}")

            drift_detected = bool(drift_details)
            safe = not drift_detected and total_found >= baseline["min_fields"]

            result = CanaryResult(
                provider=prov,
                target_fixture=str(fixture_path),
                executed_at=now,
                is_available=True,
                total_fields_found=total_found,
                required_fields_count=required_count,
                selector_failures_count=len(missing_expected),
                structural_drift_detected=drift_detected,
                drift_details=drift_details,
                safe_to_operate=safe,
            )

            if not safe:
                self._handle_canary_failure(prov, "; ".join(drift_details))
            elif self.health_mgr:
                self.health_mgr.record_success(prov)

            self.history.append(result)
            return result

        except Exception as err:
            logger.exception("Canary execution threw unhandled exception for %s: %s", prov, err)
            result = CanaryResult(
                provider=prov,
                target_fixture=str(fixture_path),
                executed_at=now,
                is_available=False,
                total_fields_found=0,
                required_fields_count=0,
                selector_failures_count=1,
                structural_drift_detected=True,
                drift_details=[f"Exception during canary inspection: {err}"],
                safe_to_operate=False,
            )
            self._handle_canary_failure(prov, str(err))
            self.history.append(result)
            return result

    def _handle_canary_failure(self, provider: str, reason: str) -> None:
        if self.health_mgr:
            self.health_mgr.record_failure(provider, failure_type="selector", reason=f"Canary failure: {reason}")
