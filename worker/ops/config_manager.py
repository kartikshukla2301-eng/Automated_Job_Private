"""Persistent Safety Configuration Manager (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 12, Appendix B)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from worker.application.models import AutonomyLevel


class SafetyConfigState(BaseModel):
    """Strongly typed persisted runtime safety configuration."""

    kill_switch_active: bool = False
    kill_switch_reason: Optional[str] = None
    daily_application_cap: int = Field(default=2, ge=1, le=50)
    per_company_daily_cap: int = Field(default=2, ge=1, le=10)
    per_company_cooldown_days: int = Field(default=30, ge=1, le=90)
    matching_threshold: float = Field(default=65.0, ge=0.0, le=100.0)
    daily_llm_budget_usd: float = Field(default=2.00, ge=0.10, le=50.0)
    provider_autonomy: Dict[str, str] = Field(
        default_factory=lambda: {
            "greenhouse": AutonomyLevel.L0.value,
            "lever": AutonomyLevel.L0.value,
        }
    )
    provider_paused: Dict[str, bool] = Field(
        default_factory=lambda: {
            "greenhouse": False,
            "lever": False,
        }
    )
    active_hours_start: int = Field(default=9, ge=0, le=23)
    active_hours_end: int = Field(default=23, ge=1, le=24)


class PersistentConfigManager:
    """Thread-safe persistent manager for runtime safety configuration."""

    def __init__(self, config_path: Path = Path("worker/sessions/app_config.json")) -> None:
        self.config_path = config_path
        self._lock = threading.Lock()
        self._state: SafetyConfigState = SafetyConfigState()
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self.config_path.exists():
                try:
                    data = json.loads(self.config_path.read_text(encoding="utf-8"))
                    self._state = SafetyConfigState.model_validate(data)
                except Exception:
                    # Fail-closed: use secure defaults
                    self._state = SafetyConfigState()
            else:
                self._save_locked()

    def _save_locked(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            self._state.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def get_state(self) -> SafetyConfigState:
        with self._lock:
            return self._state.model_copy()

    def update_caps(
        self,
        daily_cap: Optional[int] = None,
        per_company_daily_cap: Optional[int] = None,
        per_company_cooldown_days: Optional[int] = None,
    ) -> SafetyConfigState:
        with self._lock:
            updates: Dict[str, Any] = {}
            if daily_cap is not None:
                updates["daily_application_cap"] = daily_cap
            if per_company_daily_cap is not None:
                updates["per_company_daily_cap"] = per_company_daily_cap
            if per_company_cooldown_days is not None:
                updates["per_company_cooldown_days"] = per_company_cooldown_days

            self._state = self._state.model_copy(update=updates)
            self._save_locked()
            return self._state.model_copy()

    def set_provider_pause(self, provider: str, paused: bool) -> SafetyConfigState:
        with self._lock:
            paused_dict = dict(self._state.provider_paused)
            paused_dict[provider.lower()] = paused
            self._state = self._state.model_copy(update={"provider_paused": paused_dict})
            self._save_locked()
            return self._state.model_copy()

    def set_provider_autonomy(self, provider: str, level: AutonomyLevel) -> SafetyConfigState:
        with self._lock:
            autonomy_dict = dict(self._state.provider_autonomy)
            autonomy_dict[provider.lower()] = level.value
            self._state = self._state.model_copy(update={"provider_autonomy": autonomy_dict})
            self._save_locked()
            return self._state.model_copy()

    def update_llm_budget(self, budget_usd: float) -> SafetyConfigState:
        with self._lock:
            if budget_usd < 0.10:
                raise ValueError("Daily LLM budget must be at least $0.10")
            self._state = self._state.model_copy(update={"daily_llm_budget_usd": budget_usd})
            self._save_locked()
            return self._state.model_copy()
