"""Real-Submit Readiness Evaluator (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CriterionStatus(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"
    UNVERIFIED = "UNVERIFIED"


class ReadinessCriterion(BaseModel):
    id: str
    name: str
    description: str
    status: CriterionStatus
    evidence: Optional[str] = None
    missing_reason: Optional[str] = None


class ReadinessEvaluationReport(BaseModel):
    generated_at: datetime
    overall_status: CriterionStatus
    real_submit_gate_enabled: bool = False  # HARDCODED FALSE
    criteria: List[ReadinessCriterion] = Field(default_factory=list)
    summary: str


class RealSubmitReadinessEvaluator:
    """Non-executable readiness evaluator checking the 8 locked architecture gate criteria.

    CRITICAL SAFETY RULE:
    This evaluator is purely informational. It CANNOT and DOES NOT enable real submission.
    real_submit_gate_enabled remains hardcoded to False across all conditions.
    """

    def __init__(
        self,
        kill_switch_tested: bool = True,
        caps_enforced: bool = True,
        policy_golden_tests_green: bool = True,
        evidence_capture_working: bool = True,
        crash_recovery_verified: bool = True,
        telegram_alerts_verified: bool = False,
        reviewed_real_forms_count: int = 0,
        reviewed_field_accuracy: float = 0.0,
        zero_wrong_sensitive_answers: bool = True,
    ) -> None:
        self.kill_switch_tested = kill_switch_tested
        self.caps_enforced = caps_enforced
        self.policy_golden_tests_green = policy_golden_tests_green
        self.evidence_capture_working = evidence_capture_working
        self.crash_recovery_verified = crash_recovery_verified
        self.telegram_alerts_verified = telegram_alerts_verified
        self.reviewed_real_forms_count = reviewed_real_forms_count
        self.reviewed_field_accuracy = reviewed_field_accuracy
        self.zero_wrong_sensitive_answers = zero_wrong_sensitive_answers

    def evaluate(self) -> ReadinessEvaluationReport:
        now = datetime.now(timezone.utc)
        criteria: List[ReadinessCriterion] = []

        # 1. Kill switch tested
        criteria.append(
            ReadinessCriterion(
                id="G-01",
                name="Kill Switch Tested",
                description="Kill switch fail-closed enforcement and recovery verified by automated tests.",
                status=CriterionStatus.READY if self.kill_switch_tested else CriterionStatus.NOT_READY,
                evidence="Verified in tests/test_kill_switch.py and tests/test_safety_engine.py"
                if self.kill_switch_tested
                else None,
                missing_reason="Kill switch tests unverified" if not self.kill_switch_tested else None,
            )
        )

        # 2. Caps enforced
        criteria.append(
            ReadinessCriterion(
                id="G-02",
                name="Caps Enforced",
                description="Daily application and company rate caps enforced by CapsEnforcer and SafetyEngine.",
                status=CriterionStatus.READY if self.caps_enforced else CriterionStatus.NOT_READY,
                evidence="Verified in tests/test_caps.py" if self.caps_enforced else None,
                missing_reason="Caps enforcement unverified" if not self.caps_enforced else None,
            )
        )

        # 3. Policy golden tests green
        criteria.append(
            ReadinessCriterion(
                id="G-03",
                name="Policy Golden Tests",
                description="PolicyEngine taxonomic classification and rule resolution tests pass 100%.",
                status=CriterionStatus.READY if self.policy_golden_tests_green else CriterionStatus.NOT_READY,
                evidence="Verified in tests/test_policy_engine.py and tests/test_fill_plan_and_policy.py"
                if self.policy_golden_tests_green
                else None,
                missing_reason="Policy tests failing" if not self.policy_golden_tests_green else None,
            )
        )

        # 4. At least 20 real forms completed in L0 dry-run & manually reviewed
        forms_ready = self.reviewed_real_forms_count >= 20
        criteria.append(
            ReadinessCriterion(
                id="G-04",
                name="20 Real Forms Dry-Run & Reviewed",
                description="At least 20 real job forms executed in L0 dry-run and manually reviewed by human.",
                status=CriterionStatus.READY if forms_ready else CriterionStatus.NOT_READY,
                evidence=f"{self.reviewed_real_forms_count}/20 real forms reviewed" if forms_ready else None,
                missing_reason=f"Only {self.reviewed_real_forms_count}/20 real forms reviewed by operator"
                if not forms_ready
                else None,
            )
        )

        # 5. Reviewed field accuracy >= 98%
        accuracy_ready = self.reviewed_field_accuracy >= 98.0 and self.zero_wrong_sensitive_answers
        criteria.append(
            ReadinessCriterion(
                id="G-05",
                name="Reviewed Field Accuracy >= 98%",
                description="Resolved field accuracy is at least 98% with zero incorrect sensitive answers.",
                status=CriterionStatus.READY if accuracy_ready else CriterionStatus.NOT_READY,
                evidence=f"Reviewed accuracy: {self.reviewed_field_accuracy:.1f}%, 0 wrong sensitive answers"
                if accuracy_ready
                else None,
                missing_reason=f"Accuracy is {self.reviewed_field_accuracy:.1f}% (required >=98.0%) or sensitive errors present"
                if not accuracy_ready
                else None,
            )
        )

        # 6. Evidence capture working
        criteria.append(
            ReadinessCriterion(
                id="G-06",
                name="Evidence Capture Working",
                description="Full-page inspection screenshots and structured metadata captured per execution.",
                status=CriterionStatus.READY if self.evidence_capture_working else CriterionStatus.NOT_READY,
                evidence="Verified in tests/test_l0_browser_safety.py" if self.evidence_capture_working else None,
                missing_reason="Evidence capture unverified" if not self.evidence_capture_working else None,
            )
        )

        # 7. Crash recovery verified
        criteria.append(
            ReadinessCriterion(
                id="G-07",
                name="Crash Recovery Verified",
                description="Interrupted states recover safely to FAILED or UNCERTAIN without blind resubmission.",
                status=CriterionStatus.READY if self.crash_recovery_verified else CriterionStatus.NOT_READY,
                evidence="Verified in tests/test_application_orchestrator.py"
                if self.crash_recovery_verified
                else None,
                missing_reason="Crash recovery unverified" if not self.crash_recovery_verified else None,
            )
        )

        # 8. Telegram alerts verified end-to-end
        criteria.append(
            ReadinessCriterion(
                id="G-08",
                name="Telegram Alerts Verified",
                description="Telegram notifications and owner commands verified with live bot credentials.",
                status=CriterionStatus.READY if self.telegram_alerts_verified else CriterionStatus.UNVERIFIED,
                evidence="Live Telegram bot token verified" if self.telegram_alerts_verified else None,
                missing_reason="Live Telegram bot credentials unconfigured (mock adapter used for tests)"
                if not self.telegram_alerts_verified
                else None,
            )
        )

        # Overall evaluation
        has_blocked = any(c.status == CriterionStatus.BLOCKED for c in criteria)
        has_not_ready = any(c.status in (CriterionStatus.NOT_READY, CriterionStatus.UNVERIFIED) for c in criteria)

        if has_blocked:
            overall = CriterionStatus.BLOCKED
            summary = "BLOCKED: Safety gates or critical criteria are in a blocked state."
        elif has_not_ready:
            overall = CriterionStatus.NOT_READY
            ready_count = sum(1 for c in criteria if c.status == CriterionStatus.READY)
            summary = f"NOT_READY: {ready_count}/8 criteria satisfied. Real-submit gate remains strictly disabled."
        else:
            overall = CriterionStatus.READY
            summary = "All 8 criteria satisfied. NOTE: Real submission remains hardcoded disabled until explicit owner authorization."

        return ReadinessEvaluationReport(
            generated_at=now,
            overall_status=overall,
            real_submit_gate_enabled=False,  # HARDCODED FALSE
            criteria=criteria,
            summary=summary,
        )
