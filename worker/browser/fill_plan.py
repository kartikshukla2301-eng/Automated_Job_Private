"""Deterministic, explainable form fill plan data structures.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 7, 8, 11)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

from worker.browser.field_detector import DetectedField
from worker.policy.taxonomy import FieldCategory, PolicyType


class ResolutionOutcome(str, Enum):
    """Deterministic field resolution outcome status."""

    AUTO_APPROVED = "AUTO_APPROVED"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS = "AMBIGUOUS"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"


class PlannedField(BaseModel):
    """Proposed filling plan for an individual detected field.

    CRITICAL PRIVACY INVARIANT:
    `proposed_answer_ref` stores an answer key or profile property name (e.g. 'candidate.email', 'answers:notice_period').
    It NEVER stores raw passwords, SSN, OTPs, or candidate secret credentials.
    """

    model_config = ConfigDict(extra="forbid")

    field_id: str = Field(..., description="Unique field identifier on the form")
    detected_field: DetectedField = Field(..., description="Metadata of the discovered field")
    proposed_answer_ref: Optional[str] = Field(
        default=None,
        description="Safe reference to candidate profile property or Answer Bank key",
    )
    resolution_outcome: ResolutionOutcome = Field(..., description="Classification outcome")
    policy_type: PolicyType = Field(..., description="Governing policy applied by PolicyEngine")
    field_category: FieldCategory = Field(..., description="Classified taxonomy category")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in resolution")
    explanation: str = Field(..., description="Deterministic explanation for the plan")
    required_user_action: Optional[str] = Field(
        default=None,
        description="Action required from candidate if unresolved or blocked",
    )
    is_safe_to_prefill: bool = Field(
        default=False,
        description="Whether this field can be populated during future supervised execution",
    )


class FillPlan(BaseModel):
    """Deterministic, explainable form fill plan produced before any form interaction."""

    model_config = ConfigDict(extra="forbid")

    plan_id: UUID = Field(default_factory=uuid4, description="Unique plan identifier")
    session_id: UUID = Field(..., description="Associated browser session UUID")
    job_id: Optional[UUID] = Field(default=None, description="Optional job ID")
    canonical_url: str = Field(..., description="Target application page URL")
    page_title: str = Field(default="", description="Target application page title")
    fields: List[PlannedField] = Field(default_factory=list, description="Ordered field fill plans")
    total_fields: int = Field(default=0, ge=0)
    auto_approved_count: int = Field(default=0, ge=0)
    needs_review_count: int = Field(default=0, ge=0)
    blocked_count: int = Field(default=0, ge=0)
    unresolved_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when fill plan was generated",
    )

    def is_executable(self) -> bool:
        """Verify whether all required fields are resolved with auto approval or confirmation."""
        for field in self.fields:
            if field.detected_field.required:
                if field.resolution_outcome not in (
                    ResolutionOutcome.AUTO_APPROVED,
                    ResolutionOutcome.NEEDS_CONFIRMATION,
                ):
                    return False
        return True

    def get_unresolved_required_fields(self) -> List[PlannedField]:
        """Return list of mandatory form fields that require candidate intervention."""
        return [
            f for f in self.fields
            if f.detected_field.required
            and f.resolution_outcome not in (
                ResolutionOutcome.AUTO_APPROVED,
                ResolutionOutcome.NEEDS_CONFIRMATION,
            )
        ]

    def summary_dict(self) -> Dict[str, Any]:
        """Sanitized high-level summary of the fill plan without sensitive values."""
        return {
            "plan_id": str(self.plan_id),
            "session_id": str(self.session_id),
            "canonical_url": self.canonical_url,
            "total_fields": self.total_fields,
            "auto_approved_count": self.auto_approved_count,
            "needs_review_count": self.needs_review_count,
            "blocked_count": self.blocked_count,
            "unresolved_count": self.unresolved_count,
            "is_executable": self.is_executable(),
        }
