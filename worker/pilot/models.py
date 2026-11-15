"""Models for Live L0 Form-Inspection Pilot and Evidence Validation (Phase 2.1).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field


class PilotReviewStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FLAGGED = "FLAGGED"


class PilotFormRecord(BaseModel):
    """Structured record of an operator-controlled L0 form inspection."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4, description="Unique pilot inspection record ID")
    user_id: UUID = Field(..., description="Candidate/operator user ID")
    provider: str = Field(..., description="Provider identifier (greenhouse, lever, ashby, naukri, etc.)")
    job_id: str = Field(..., description="External job posting identifier or canonical key")
    job_url: str = Field(..., description="Job application URL")
    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Job title")
    inspected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Form metrics
    fields_count: int = Field(default=0, ge=0)
    resolved_count: int = Field(default=0, ge=0)
    unresolved_count: int = Field(default=0, ge=0)
    policy_blocked_count: int = Field(default=0, ge=0)
    sensitive_fields_count: int = Field(default=0, ge=0)

    # Evidence details
    evidence_dir: Optional[str] = Field(default=None, description="Local directory path to evidence package")
    screenshot_path: Optional[str] = Field(default=None, description="Path to captured screenshot")
    schema_snapshot: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted form fields metadata")
    fill_plan: Dict[str, Any] = Field(default_factory=dict, description="Generated truthful fill plan")

    # Human review tracking
    review_status: PilotReviewStatus = Field(default=PilotReviewStatus.PENDING)
    reviewed_at: Optional[datetime] = Field(default=None)
    reviewer_id: Optional[str] = Field(default=None)
    reviewer_notes: Optional[str] = Field(default=None)
    incorrect_mappings_count: int = Field(default=0, ge=0)
    wrong_sensitive_count: int = Field(default=0, ge=0)

    # Provenance tracking
    is_live_page: bool = Field(default=True, description="True if inspected on a live URL; False if offline capture")
    audit_hash: Optional[str] = Field(default=None, description="SHA-256 integrity hash of inspection schema")


class PilotReviewRequest(BaseModel):
    """Payload submitted by human operator upon reviewing a pilot form."""

    model_config = ConfigDict(extra="forbid")

    status: PilotReviewStatus = Field(..., description="Review outcome (APPROVED, REJECTED, FLAGGED)")
    reviewer_id: str = Field(default="operator", description="Operator username or identifier")
    notes: Optional[str] = Field(default=None, description="Review feedback or explanation")
    incorrect_mappings_count: int = Field(default=0, ge=0, description="Count of incorrect field resolutions")
    wrong_sensitive_count: int = Field(default=0, ge=0, description="Count of sensitive security fields mis-mapped")


class PilotQualityReport(BaseModel):
    """Truthful aggregate report of L0 pilot quality and gate readiness."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_inspections: int = Field(default=0, ge=0)
    distinct_forms_inspected: int = Field(default=0, ge=0)
    forms_reviewed: int = Field(default=0, ge=0)
    forms_pending_review: int = Field(default=0, ge=0)

    # Accuracy calculations (explicitly documented methodology)
    total_reviewed_fields: int = Field(default=0, ge=0)
    total_reviewed_resolved: int = Field(default=0, ge=0)
    total_incorrect_mappings: int = Field(default=0, ge=0)
    total_wrong_sensitive_answers: int = Field(default=0, ge=0)
    reviewed_field_accuracy: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Calculated as (total_reviewed_resolved - incorrect_mappings) / total_reviewed_resolved * 100",
    )
    accuracy_methodology: str = Field(
        default="Accuracy = max(0, (resolved_correct) / (resolved_correct + incorrect_mappings)) * 100. "
        "Unresolved fields are NOT treated as correct mappings.",
        description="Explicit description of accuracy calculation formula",
    )

    # Provider breakdown
    provider_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    duplicate_records_detected: int = Field(default=0, ge=0)
    is_gate_ready: bool = Field(
        default=False,
        description="True only if distinct_forms_inspected >= 20, forms_reviewed >= 20, "
        "accuracy >= 98.0%, and wrong_sensitive == 0.",
    )
