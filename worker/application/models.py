"""Canonical Application lifecycle data models and event structures.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 13, 14)
- migrations/001_initial_schema.sql (applications, application_events schemas)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ApplicationStatus(str, Enum):
    """Exact application status values matching PostgreSQL check constraint `ck_applications_status`."""

    DISCOVERED = "DISCOVERED"
    MATCHED = "MATCHED"
    ELIGIBLE = "ELIGIBLE"
    READY = "READY"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    FILLING = "FILLING"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    BLOCKED = "BLOCKED"
    SUBMITTING = "SUBMITTING"
    UNCERTAIN = "UNCERTAIN"
    VERIFYING = "VERIFYING"
    APPLIED = "APPLIED"
    DRY_RUN_DONE = "DRY_RUN_DONE"
    SKIPPED = "SKIPPED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    DUPLICATE = "DUPLICATE"
    FAILED = "FAILED"


class AutonomyLevel(str, Enum):
    """Autonomy levels matching PostgreSQL check constraint `ck_applications_autonomy`."""

    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class ApprovalStatus(str, Enum):
    """Approval gate status values."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApplicationEventType(str, Enum):
    """Canonical event types for audit ledger in `application_events`."""

    CREATED = "CREATED"
    STATE_TRANSITION = "STATE_TRANSITION"
    MATCH_EVALUATED = "MATCH_EVALUATED"
    SAFETY_VERIFIED = "SAFETY_VERIFIED"
    SAFETY_BLOCKED = "SAFETY_BLOCKED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    INPUT_REQUESTED = "INPUT_REQUESTED"
    INPUT_RESOLVED = "INPUT_RESOLVED"
    DRY_RUN_STARTED = "DRY_RUN_STARTED"
    DRY_RUN_COMPLETED = "DRY_RUN_COMPLETED"
    DRY_RUN_FAILED = "DRY_RUN_FAILED"
    SUBMIT_INTENT = "SUBMIT_INTENT"
    SUBMIT_ATTEMPTED = "SUBMIT_ATTEMPTED"
    SUBMISSION_VERIFIED = "SUBMISSION_VERIFIED"
    RECOVERY_INITIATED = "RECOVERY_INITIATED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"


class Application(BaseModel):
    """Canonical Application model matching `applications` table schema."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4, description="Primary key UUID")
    user_id: UUID = Field(..., description="Foreign key to auth.users")
    job_id: UUID = Field(..., description="Foreign key to jobs")
    platform: str = Field(..., min_length=1, max_length=50, description="Provider platform (e.g. greenhouse, lever)")
    external_id: str = Field(..., min_length=1, max_length=255, description="Provider unique job identifier")
    profile_version: str = Field(..., min_length=1, max_length=64, description="Profile snapshot version hash")
    resume_version: Optional[str] = Field(default=None, max_length=32, description="Target resume variant version")
    autonomy_level: AutonomyLevel = Field(default=AutonomyLevel.L0, description="Autonomy level (L0-L3)")
    status: ApplicationStatus = Field(default=ApplicationStatus.DISCOVERED, description="Current lifecycle state")
    score: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Matching score (0-100)")
    score_breakdown: Dict[str, Any] = Field(default_factory=dict, description="Factor-level score breakdown")
    approval_status: Optional[ApprovalStatus] = Field(default=None, description="Approval gate state")
    approved_at: Optional[datetime] = Field(default=None, description="Timestamp of user approval")
    idempotency_key: str = Field(..., min_length=1, max_length=128, description="Deterministic idempotency token")
    fields_filled: Dict[str, Any] = Field(default_factory=dict, description="Resolved form fields payload")
    evidence_ref: Optional[str] = Field(default=None, description="Path to captured screenshot or DOM audit artifact")
    run_id: Optional[UUID] = Field(default=None, description="Execution run correlation UUID")
    error: Optional[str] = Field(default=None, description="Sanitized failure reason if failed")
    applied_at: Optional[datetime] = Field(default=None, description="Timestamp of verified submission (None in L0)")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record update timestamp",
    )


class ApplicationEvent(BaseModel):
    """Audit trail record corresponding to `application_events` schema."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4, description="Primary key UUID")
    application_id: UUID = Field(..., description="Foreign key to applications")
    event_type: str = Field(..., min_length=1, max_length=100, description="Event classification")
    previous_status: Optional[ApplicationStatus] = Field(default=None, description="Status prior to event")
    new_status: Optional[ApplicationStatus] = Field(default=None, description="Status resulting from event")
    reason: Optional[str] = Field(default=None, description="Human-readable rationale or diagnostic message")
    triggering_component: Optional[str] = Field(default=None, description="Service or module initiating event")
    run_id: Optional[UUID] = Field(default=None, description="Correlation run UUID")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Safe structured metadata (PII-redacted)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC event occurrence timestamp",
    )
