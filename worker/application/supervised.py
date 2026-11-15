"""L1 Supervised Execution Preparation and Pre-Submission Simulation (Phase 2.7).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12, 13)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from worker.application.models import Application, ApplicationStatus, AutonomyLevel
from worker.core.exceptions import (
    CapExceededError,
    KillSwitchActiveError,
    RealSubmitGateBlockedError,
    SafetyBlockedError,
)
from worker.core.safety import SafetyEngine
from worker.ops.provider_health import ProviderHealthManager

logger = logging.getLogger("worker.application.supervised")


class PreSubmissionSimulationReport(BaseModel):
    """Detailed report resulting from pre-submission inspection and safety checks."""

    model_config = ConfigDict(extra="forbid")

    application_id: UUID
    job_id: UUID
    platform: str
    company: str
    autonomy_level: AutonomyLevel = AutonomyLevel.L1
    can_proceed_to_pre_submit: bool
    fill_plan_field_count: int = 0
    resolved_fields: List[str] = Field(default_factory=list)
    sensitive_fields: List[str] = Field(default_factory=list)
    safety_checks_passed: bool = False
    blocking_reasons: List[str] = Field(default_factory=list)
    simulated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    real_submit_gate_status: str = Field(
        default="LOCKED_DISABLED",
        description="Real submit gate is unconditionally hardcoded to False.",
    )


class SupervisedExecutionSimulator:
    """Orchestrates L1 pre-submission simulation under human supervision.

    Enforces the non-negotiable architectural invariant:
    Real submission is strictly disabled (real_submit_gate_enabled = False).
    Simulation verifies all pre-conditions, builds the fill plan, reviews all
    sensitive fields, and stops completely before clicking or submitting.
    """

    def __init__(
        self,
        safety_engine: Optional[SafetyEngine] = None,
        provider_health_mgr: Optional[ProviderHealthManager] = None,
    ) -> None:
        self.safety_engine = safety_engine
        self.provider_health_mgr = provider_health_mgr
        # Strictly hardcoded barrier
        self.real_submit_gate_enabled: bool = False

    async def simulate_pre_submission(
        self,
        application: Application,
        company: str,
        fill_plan: Dict[str, Any],
        attempt_real_submit: bool = False,
    ) -> PreSubmissionSimulationReport:
        """Execute pre-submission safety verification and simulation.

        Stops strictly before any submit action.
        """
        # Hard barrier check: reject any live submission attempt immediately
        if attempt_real_submit or self.real_submit_gate_enabled:
            raise RealSubmitGateBlockedError(
                "Real submission gate is hardcoded disabled in locked architecture. "
                "Only supervised simulations and dry-runs are permitted."
            )

        blocking: List[str] = []

        # 1. Verify SafetyEngine barrier (kill switch + rate caps + cooldown)
        if self.safety_engine:
            try:
                self.safety_engine.verify_pre_apply(
                    company=company,
                    provider=application.platform,
                    is_real_submit=False,
                )
            except KillSwitchActiveError as ex:
                blocking.append(f"Kill switch active: {ex}")
            except CapExceededError as ex:
                blocking.append(f"Application cap exceeded: {ex}")
            except SafetyBlockedError as ex:
                blocking.append(f"Safety barrier blocked: {ex}")

        # 2. Verify Provider Health
        if self.provider_health_mgr:
            health = self.provider_health_mgr.get_state(application.platform)
            if health and health.status.value != "HEALTHY":
                blocking.append(
                    f"Provider '{application.platform}' is in status '{health.status.value}' "
                    f"(consecutive failures: {health.consecutive_failures})"
                )

        # 3. Verify Fill Plan integrity and detect sensitive / expired answers
        fields = fill_plan.get("fields", [])
        resolved_fields: List[str] = []
        sensitive_fields: List[str] = []

        for field in fields:
            name = field.get("name", "unknown")
            policy = field.get("policy", "")
            is_sensitive = field.get("is_sensitive", False) or policy in ("always_ask", "never_fill")

            if is_sensitive:
                sensitive_fields.append(name)

            if field.get("is_expired", False):
                blocking.append(f"Field '{name}' has expired answer in Answer Bank")

            if field.get("value") is not None:
                resolved_fields.append(name)
            elif field.get("required", False):
                blocking.append(f"Required field '{name}' is unresolved")

        can_proceed = (len(blocking) == 0)

        logger.info(
            "Completed L1 pre-submission simulation for app %s (%s at %s). Result: %s (blocks: %d)",
            application.id,
            application.platform,
            company,
            "PASS" if can_proceed else "BLOCKED",
            len(blocking),
        )

        return PreSubmissionSimulationReport(
            application_id=application.id,
            job_id=application.job_id,
            platform=application.platform,
            company=company,
            autonomy_level=application.autonomy_level,
            can_proceed_to_pre_submit=can_proceed,
            fill_plan_field_count=len(fields),
            resolved_fields=resolved_fields,
            sensitive_fields=sensitive_fields,
            safety_checks_passed=can_proceed,
            blocking_reasons=blocking,
            real_submit_gate_status="LOCKED_DISABLED",
        )
