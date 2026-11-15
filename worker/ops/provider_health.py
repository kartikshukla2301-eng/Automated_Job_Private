"""Provider Health Tracking and Auto-Pause Management (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import logging
import threading
from typing import Callable, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProviderStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    PAUSED = "PAUSED"


class ProviderHealthState(BaseModel):
    """Health metrics and operational status for an individual provider."""

    provider_name: str
    status: ProviderStatus = ProviderStatus.HEALTHY
    successful_inspections: int = 0
    navigation_failures: int = 0
    selector_failures: int = 0
    browser_crashes: int = 0
    session_expiries: int = 0
    timeouts: int = 0
    consecutive_failures: int = 0
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_failure_reason: Optional[str] = None
    paused_at: Optional[datetime] = None
    pause_reason: Optional[str] = None


class ProviderHealthManager:
    """Monitors provider reliability and triggers automatic fail-closed pauses.

    Architecture Rule:
    - 3 consecutive failures in any provider automatically triggers auto-pause for that provider.
    - Other healthy providers remain unaffected.
    - Manual resume is required to unpause; autonomy is never auto-promoted upon unpause.
    """

    def __init__(
        self,
        max_consecutive_failures: int = 3,
        on_auto_pause_callback: Optional[Callable[[str, str, int], None]] = None,
    ) -> None:
        self.max_consecutive_failures = max_consecutive_failures
        self.on_auto_pause = on_auto_pause_callback
        self._lock = threading.Lock()
        self._states: Dict[str, ProviderHealthState] = {}

    def get_or_create_state(self, provider: str) -> ProviderHealthState:
        with self._lock:
            key = provider.lower()
            if key not in self._states:
                self._states[key] = ProviderHealthState(provider_name=key)
            return self._states[key].model_copy()

    def get_all_states(self) -> Dict[str, ProviderHealthState]:
        with self._lock:
            return {k: v.model_copy() for k, v in self._states.items()}

    def is_provider_available(self, provider: str) -> bool:
        """Check if provider is operational (not paused)."""
        with self._lock:
            key = provider.lower()
            state = self._states.get(key)
            if not state:
                return True
            return state.status != ProviderStatus.PAUSED

    def record_success(self, provider: str) -> ProviderHealthState:
        """Record successful execution/inspection; resets consecutive failure counter."""
        with self._lock:
            key = provider.lower()
            state = self._states.get(key) or ProviderHealthState(provider_name=key)
            now = datetime.now(timezone.utc)

            new_status = ProviderStatus.HEALTHY if state.status != ProviderStatus.PAUSED else ProviderStatus.PAUSED

            state = state.model_copy(
                update={
                    "successful_inspections": state.successful_inspections + 1,
                    "consecutive_failures": 0,
                    "last_success_at": now,
                    "status": new_status,
                }
            )
            self._states[key] = state
            return state.model_copy()

    def record_failure(
        self,
        provider: str,
        failure_type: str,
        reason: str,
    ) -> ProviderHealthState:
        """Record a failure event (navigation, selector, timeout, crash).

        If consecutive_failures reaches threshold, automatically transitions to PAUSED.
        """
        auto_pause_triggered = False
        with self._lock:
            key = provider.lower()
            state = self._states.get(key) or ProviderHealthState(provider_name=key)
            now = datetime.now(timezone.utc)

            nav_fails = state.navigation_failures + (1 if failure_type == "navigation" else 0)
            sel_fails = state.selector_failures + (1 if failure_type == "selector" else 0)
            crash_fails = state.browser_crashes + (1 if failure_type == "crash" else 0)
            timeout_fails = state.timeouts + (1 if failure_type == "timeout" else 0)
            session_fails = state.session_expiries + (1 if failure_type == "session_expiry" else 0)

            new_consecutive = state.consecutive_failures + 1
            new_status = state.status

            pause_reason = state.pause_reason
            paused_at = state.paused_at

            if new_consecutive >= self.max_consecutive_failures and state.status != ProviderStatus.PAUSED:
                new_status = ProviderStatus.PAUSED
                paused_at = now
                pause_reason = (
                    f"Auto-paused after {new_consecutive} consecutive failures. Latest: {failure_type} ({reason})"
                )
                auto_pause_triggered = True
                logger.error(
                    "Provider %s automatically PAUSED due to %s consecutive failures: %s",
                    key,
                    new_consecutive,
                    reason,
                )
            elif new_consecutive > 1 and state.status != ProviderStatus.PAUSED:
                new_status = ProviderStatus.DEGRADED

            state = state.model_copy(
                update={
                    "navigation_failures": nav_fails,
                    "selector_failures": sel_fails,
                    "browser_crashes": crash_fails,
                    "timeouts": timeout_fails,
                    "session_expiries": session_fails,
                    "consecutive_failures": new_consecutive,
                    "last_failure_at": now,
                    "last_failure_reason": f"[{failure_type}] {reason}",
                    "status": new_status,
                    "paused_at": paused_at,
                    "pause_reason": pause_reason,
                }
            )
            self._states[key] = state

        if auto_pause_triggered and self.on_auto_pause:
            try:
                self.on_auto_pause(key, reason, new_consecutive)
            except Exception as cb_err:
                logger.error("Error in on_auto_pause callback for %s: %s", key, cb_err)

        return state.model_copy()

    def pause_provider(self, provider: str, reason: str = "Manually paused by operator") -> ProviderHealthState:
        """Manually pause a provider."""
        with self._lock:
            key = provider.lower()
            state = self._states.get(key) or ProviderHealthState(provider_name=key)
            now = datetime.now(timezone.utc)
            state = state.model_copy(
                update={
                    "status": ProviderStatus.PAUSED,
                    "paused_at": now,
                    "pause_reason": reason,
                }
            )
            self._states[key] = state
            logger.warning("Provider %s manually PAUSED: %s", key, reason)
            return state.model_copy()

    def resume_provider(self, provider: str) -> ProviderHealthState:
        """Manually resume a paused provider; resets consecutive failures to 0."""
        with self._lock:
            key = provider.lower()
            state = self._states.get(key) or ProviderHealthState(provider_name=key)
            state = state.model_copy(
                update={
                    "status": ProviderStatus.HEALTHY,
                    "consecutive_failures": 0,
                    "paused_at": None,
                    "pause_reason": None,
                }
            )
            self._states[key] = state
            logger.info("Provider %s manually RESUMED (status: HEALTHY)", key)
            return state.model_copy()
