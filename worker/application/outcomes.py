"""Application post-submission outcome and milestone tracking (Phase 1.9).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 13, 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("worker.application.outcomes")


class OutcomeMilestone(str, Enum):
    """Post-application interview and offer stages recorded by the user."""

    INTERVIEW_SCHEDULED = "INTERVIEW_SCHEDULED"
    TECHNICAL_SCREEN = "TECHNICAL_SCREEN"
    ONSITE_INTERVIEW = "ONSITE_INTERVIEW"
    OFFER_RECEIVED = "OFFER_RECEIVED"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    REJECTED_BY_COMPANY = "REJECTED_BY_COMPANY"
    WITHDRAWN_BY_CANDIDATE = "WITHDRAWN_BY_CANDIDATE"


class ApplicationOutcomeRecord(BaseModel):
    """Immutable record tracking an application outcome milestone."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    application_id: str = Field(..., description="ID of associated job application")
    milestone: OutcomeMilestone = Field(..., description="Stage or outcome milestone")
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_timestamp: Optional[datetime] = Field(default=None, description="Timestamp of interview/offer if specific")
    notes: Optional[str] = Field(default=None, description="Optional user notes or interview feedback")
    recruiter_contact: Optional[str] = Field(default=None, description="Recruiter or interviewer contact details")
    offer_amount: Optional[float] = Field(default=None, description="Stated compensation if offer received")


class OutcomeTracker:
    """Manages application outcome milestones in thread-safe persistence."""

    def __init__(self, storage_path: Path = Path("worker/application/outcomes.json")) -> None:
        self.storage_path = storage_path

    def _load(self) -> List[Dict[str, Any]]:
        if not self.storage_path.exists():
            return []
        try:
            return json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception as err:
            logger.warning("Could not read application outcomes storage: %s", err)
            return []

    def _save(self, records: List[Dict[str, Any]]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def record_milestone(
        self,
        application_id: str,
        milestone: OutcomeMilestone,
        event_timestamp: Optional[datetime] = None,
        notes: Optional[str] = None,
        recruiter_contact: Optional[str] = None,
        offer_amount: Optional[float] = None,
    ) -> ApplicationOutcomeRecord:
        """Record an outcome milestone for a job application."""
        record = ApplicationOutcomeRecord(
            application_id=application_id,
            milestone=milestone,
            event_timestamp=event_timestamp,
            notes=notes,
            recruiter_contact=recruiter_contact,
            offer_amount=offer_amount,
        )

        existing = self._load()
        existing.append(record.model_dump(mode="json"))
        self._save(existing)
        logger.info("Recorded outcome milestone '%s' for application '%s'", milestone.value, application_id)
        return record

    def get_outcomes_for_application(self, application_id: str) -> List[ApplicationOutcomeRecord]:
        """Retrieve all recorded outcome milestones for an application."""
        records = self._load()
        return [
            ApplicationOutcomeRecord(**r)
            for r in records
            if r.get("application_id") == str(application_id)
        ]

    def list_all_outcomes(self) -> List[ApplicationOutcomeRecord]:
        """List all recorded outcomes across all applications."""
        records = self._load()
        return [ApplicationOutcomeRecord(**r) for r in records]
