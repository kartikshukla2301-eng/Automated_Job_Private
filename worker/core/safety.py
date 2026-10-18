"""Unified safety engine and pre-application execution boundary."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from worker.core.caps import CapsEnforcer
from worker.core.exceptions import (
    CapExceededError,
    InvalidSafetyStateError,
    KillSwitchActiveError,
    RealSubmitGateBlockedError,
    SafetyBlockedError,
)
from worker.core.kill_switch import KillSwitch


class SafetyDecision(BaseModel):
    """Explicit decision returned by the safety engine before application actions."""

    allowed: bool = Field(..., description="True if application action is permitted; False otherwise.")
    reason: str = Field(..., description="Human-readable explanation of the safety decision.")
    blocked_by: Optional[str] = Field(
        default=None,
        description="Categorical identifier of the blocker (e.g. kill_switch, caps, real_submit_gate).",
    )


class SafetyEngine:
    """Pre-application safety barrier coordinating kill switch, caps, and real-submit gate.

    MANDATORY EXECUTION BOUNDARY CONTRACT (Architecture v1.0 LOCKED):
    - All job execution code (including provider adapters such as Greenhouse/Lever)
      must be mediated by a central runner that calls verify_pre_apply() before
      initiating any form navigation, answer filling, or browser interaction.
    - Direct invocation of browser automation without passing through this barrier
      is strictly forbidden by architecture rules.
    - Real job submissions are strictly locked (real_submit_gate_enabled=False)
      until all locked gates in Section 13 (line 683) are formally validated.
    """

    def __init__(
        self,
        kill_switch: KillSwitch,
        caps_enforcer: CapsEnforcer,
        real_submit_gate_enabled: bool = False,
    ) -> None:
        """Initialize SafetyEngine.

        Args:
            kill_switch: Component providing automation enable/disable state.
            caps_enforcer: Component enforcing rate limits and cooldowns.
            real_submit_gate_enabled: Master flag for real job submissions.
                MANDATORY: Defaults to False until all locked gates pass.
        """
        self.kill_switch = kill_switch
        self.caps_enforcer = caps_enforcer
        self.real_submit_gate_enabled = real_submit_gate_enabled

    def verify_pre_apply(
        self,
        company: str,
        provider: str,
        is_real_submit: bool = False,
        now: Optional[datetime] = None,
    ) -> None:
        """Verify all safety criteria before any application attempt.

        Raises:
            KillSwitchActiveError: When automation is blocked by the kill switch.
            InvalidSafetyStateError: When safety state is missing/corrupted.
            RealSubmitGateBlockedError: When real submission is attempted without locked gate clearance.
            CapExceededError: When daily or cooldown rate caps are exceeded.
        """
        # 1. Kill Switch verification (fail closed)
        self.kill_switch.verify_automation_allowed()

        # 2. Real-submit gate check
        if is_real_submit and not self.real_submit_gate_enabled:
            raise RealSubmitGateBlockedError(
                "Real job submission blocked: Architecture v1.0 locked Real-Submit Gate criteria not yet fulfilled."
            )

        # 3. Application caps verification
        self.caps_enforcer.check_caps(company=company, provider=provider, now=now)

    def evaluate_pre_apply(
        self,
        company: str,
        provider: str,
        is_real_submit: bool = False,
        now: Optional[datetime] = None,
    ) -> SafetyDecision:
        """Evaluate safety criteria and return an explicit, non-throwing decision."""
        try:
            self.verify_pre_apply(
                company=company,
                provider=provider,
                is_real_submit=is_real_submit,
                now=now,
            )
            return SafetyDecision(
                allowed=True,
                reason="All safety checks passed (kill switch clear, caps within limits, submission permitted).",
            )
        except KillSwitchActiveError as exc:
            return SafetyDecision(
                allowed=False,
                reason=str(exc),
                blocked_by="kill_switch",
            )
        except InvalidSafetyStateError as exc:
            return SafetyDecision(
                allowed=False,
                reason=str(exc),
                blocked_by="invalid_safety_state",
            )
        except RealSubmitGateBlockedError as exc:
            return SafetyDecision(
                allowed=False,
                reason=str(exc),
                blocked_by="real_submit_gate",
            )
        except CapExceededError as exc:
            return SafetyDecision(
                allowed=False,
                reason=str(exc),
                blocked_by="application_caps",
            )
        except SafetyBlockedError as exc:
            return SafetyDecision(
                allowed=False,
                reason=str(exc),
                blocked_by="safety_blocked",
            )
