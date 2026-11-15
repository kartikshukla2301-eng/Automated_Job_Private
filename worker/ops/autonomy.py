"""Autonomy Control and Capacity Ramp Foundation (Phase 1.6).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12, Appendix B)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from worker.application.models import AutonomyLevel

logger = logging.getLogger(__name__)


class CapacityStage(str, Enum):
    S0 = "S0"  # L0 Dry-Run (20 dry runs, >=98% accuracy)
    S1 = "S1"  # L1 Supervised (up to 15/day, 30 approved apps, 0 wrong sensitive)
    S2 = "S2"  # L2 Assisted Auto (up to 40/day, 0 duplicates, declining user interventions)
    S3 = "S3"  # L3 Full Auto (60 -> 100 -> 150/day, stable KPIs for 2 weeks)


class AutonomyEligibilityReport(BaseModel):
    provider: str
    current_level: AutonomyLevel
    eligible_for_next_level: bool
    target_level: Optional[AutonomyLevel] = None
    applications_at_current_level: int
    reviewed_accuracy_percent: float
    wrong_sensitive_answers_count: int
    duplicate_applications_count: int
    missing_requirements: List[str] = Field(default_factory=list)
    blocking_conditions: List[str] = Field(default_factory=list)
    can_auto_promote: bool = False  # NEVER auto-promotes without explicit owner authorization


class CapacityStageReport(BaseModel):
    current_stage: CapacityStage
    target_stage: Optional[CapacityStage] = None
    is_eligible_for_advance: bool
    active_daily_cap: int = 2  # Hardcoded default; never auto-increased
    daily_cap_target: int
    requirements_met: List[str] = Field(default_factory=list)
    missing_requirements: List[str] = Field(default_factory=list)
    blocking_conditions: List[str] = Field(default_factory=list)


class AutonomyController:
    """Tracks provider autonomy levels, evaluates promotion readiness, and enforces automatic demotion."""

    def __init__(self) -> None:
        # Default all providers to L0
        self._provider_levels: Dict[str, AutonomyLevel] = {
            "greenhouse": AutonomyLevel.L0,
            "lever": AutonomyLevel.L0,
            "naukri": AutonomyLevel.L0,
            "wellfound": AutonomyLevel.L0,
            "ashby": AutonomyLevel.L0,
            "linkedin": AutonomyLevel.L0,
        }

    def get_level(self, provider: str) -> AutonomyLevel:
        return self._provider_levels.get(provider.lower(), AutonomyLevel.L0)

    def set_level_by_owner(self, provider: str, level: AutonomyLevel, actor: str = "owner") -> None:
        """Owner explicitly authorizes a level change."""
        prov = provider.lower()
        if prov == "linkedin" and level in (AutonomyLevel.L2, AutonomyLevel.L3):
            raise ValueError("LinkedIn is a restricted provider: maximum permitted autonomy level is L1")
        old_level = self.get_level(prov)
        self._provider_levels[prov] = level
        logger.info(
            "Autonomy level for %s changed by %s from %s to %s",
            prov,
            actor,
            old_level.value,
            level.value,
        )

    def trigger_automatic_demotion(self, provider: str, reason: str) -> AutonomyLevel:
        """Automatically demote provider to L1 (or L0 if already at L0) upon safety violations.

        Demotion triggers:
        - Policy violation
        - Selector failure spike
        - Form structural change detected by canary
        - Unexplained duplicate
        """
        prov = provider.lower()
        current = self.get_level(prov)
        # Demote to L1 or keep L0
        target = AutonomyLevel.L0 if current == AutonomyLevel.L0 else AutonomyLevel.L1
        self._provider_levels[prov] = target
        logger.warning(
            "SAFETY DEMOTION: Provider %s demoted from %s to %s. Reason: %s",
            prov,
            current.value,
            target.value,
            reason,
        )
        return target

    def evaluate_eligibility(
        self,
        provider: str,
        total_apps_at_level: int,
        reviewed_accuracy: float,
        wrong_sensitive_count: int,
        duplicate_count: int,
    ) -> AutonomyEligibilityReport:
        """Evaluate promotion criteria against locked architecture rules:

        - At least 30 applications at current level.
        - Zero wrong sensitive answers.
        - Zero duplicate applications.
        - Reviewed field accuracy >= 98.0%.
        """
        prov = provider.lower()
        current = self.get_level(prov)

        next_level_map = {
            AutonomyLevel.L0: AutonomyLevel.L1,
            AutonomyLevel.L1: AutonomyLevel.L2,
            AutonomyLevel.L2: AutonomyLevel.L3,
            AutonomyLevel.L3: None,
        }
        target = next_level_map.get(current)

        missing: List[str] = []
        blocking: List[str] = []

        if target is None:
            return AutonomyEligibilityReport(
                provider=prov,
                current_level=current,
                eligible_for_next_level=False,
                target_level=None,
                applications_at_current_level=total_apps_at_level,
                reviewed_accuracy_percent=reviewed_accuracy,
                wrong_sensitive_answers_count=wrong_sensitive_count,
                duplicate_applications_count=duplicate_count,
                missing_requirements=["Already at highest autonomy level (L3)"],
            )

        if prov == "linkedin" and target in (AutonomyLevel.L2, AutonomyLevel.L3):
            blocking.append("LinkedIn is restricted: capped at L1 autonomy and prohibited from L2/L3 promotion")

        if total_apps_at_level < 30:
            missing.append(f"Requires >= 30 applications at {current.value} (currently {total_apps_at_level})")

        if reviewed_accuracy < 98.0:
            missing.append(f"Reviewed field accuracy must be >= 98.0% (currently {reviewed_accuracy:.1f}%)")

        if wrong_sensitive_count > 0:
            blocking.append(f"Zero wrong sensitive answers required (recorded {wrong_sensitive_count})")

        if duplicate_count > 0:
            blocking.append(f"Zero duplicate applications required (recorded {duplicate_count})")

        eligible = len(missing) == 0 and len(blocking) == 0

        return AutonomyEligibilityReport(
            provider=prov,
            current_level=current,
            eligible_for_next_level=eligible,
            target_level=target,
            applications_at_current_level=total_apps_at_level,
            reviewed_accuracy_percent=reviewed_accuracy,
            wrong_sensitive_answers_count=wrong_sensitive_count,
            duplicate_applications_count=duplicate_count,
            missing_requirements=missing,
            blocking_conditions=blocking,
            can_auto_promote=False,  # Explicit owner approval is required
        )

    def evaluate_capacity_stage(
        self,
        current_stage: CapacityStage,
        completed_dry_runs: int,
        approved_apps_total: int,
        accuracy_percent: float,
        policy_violations_count: int,
        duplicates_count: int,
    ) -> CapacityStageReport:
        """Evaluate capacity ramp stage readiness (S0 -> S1 -> S2 -> S3)."""
        missing: List[str] = []
        blocking: List[str] = []
        met: List[str] = []

        if current_stage == CapacityStage.S0:
            target_stage = CapacityStage.S1
            daily_target = 15
            if completed_dry_runs >= 20:
                met.append(f"{completed_dry_runs}/20 dry-runs completed")
            else:
                missing.append(f"Need >=20 dry-runs (completed {completed_dry_runs})")

            if accuracy_percent >= 98.0:
                met.append(f"Accuracy {accuracy_percent:.1f}% >= 98.0%")
            else:
                missing.append(f"Accuracy must be >= 98.0% (currently {accuracy_percent:.1f}%)")

            if policy_violations_count == 0:
                met.append("Zero policy violations")
            else:
                blocking.append(f"Zero policy violations required (found {policy_violations_count})")

        elif current_stage == CapacityStage.S1:
            target_stage = CapacityStage.S2
            daily_target = 40
            if approved_apps_total >= 30:
                met.append(f"{approved_apps_total}/30 approved applications completed")
            else:
                missing.append(f"Need >=30 approved applications (current: {approved_apps_total})")

            if duplicates_count == 0:
                met.append("Zero duplicates")
            else:
                blocking.append(f"Zero duplicates required (found {duplicates_count})")

        else:
            target_stage = None
            daily_target = 100

        eligible = len(missing) == 0 and len(blocking) == 0

        return CapacityStageReport(
            current_stage=current_stage,
            target_stage=target_stage,
            is_eligible_for_advance=eligible,
            active_daily_cap=2,  # DAILY CAP REMAINS LOCKED AT 2
            daily_cap_target=daily_target,
            requirements_met=met,
            missing_requirements=missing,
            blocking_conditions=blocking,
        )
