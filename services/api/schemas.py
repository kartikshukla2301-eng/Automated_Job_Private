"""Pydantic schemas for FastAPI endpoints."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for GET /health response."""

    status: str = Field(..., description="Service health status", examples=["healthy"])
    service: str = Field(..., description="Service identifier", examples=["job-agent-api"])
    version: str = Field(..., description="Service semantic version", examples=["0.1.0"])
    environment: str = Field(..., description="Operating environment", examples=["development"])


class GreenhouseDryRunRequest(BaseModel):
    """Request schema for executing a safe Greenhouse local fixture dry run.

    SECURITY RULE:
    Arbitrary URLs, filesystem paths, or unexpected parameters are strictly
    forbidden by schema validation. Execution is bound to the approved fixture.
    """

    model_config = {"extra": "forbid"}

    company: str = Field(
        default="Example Software",
        description="Target employer company name matching the approved fixture",
        max_length=100,
    )


class GreenhouseDryRunResponse(BaseModel):
    """Auditable response returned by the dry-run execution."""

    job_url: str = Field(..., description="Target job fixture URI")
    company: str = Field(..., description="Target company name")
    provider: str = Field(..., description="Job board provider name")
    profile_version: str = Field(..., description="Candidate profile version hash used for filling")
    fields_filled: dict[str, str] = Field(
        default_factory=dict,
        description="Fields truthfully resolved and filled into the form",
    )
    unresolved_fields: list[str] = Field(
        default_factory=list,
        description="Fields requiring user review or Answer Bank resolution",
    )
    screenshot_path: str | None = Field(
        default=None,
        description="Path to captured full-page form evidence screenshot",
    )
    status: str = Field(..., description="Execution lifecycle status")
    executed_at: str = Field(..., description="ISO-8601 UTC timestamp of execution")
    safety_allowed: bool = Field(default=True, description="Whether pre-apply safety barrier allowed execution")
    safety_reason: str = Field(..., description="Explanation of safety barrier decision")


class SafetyErrorResponse(BaseModel):
    """Structured error response when safety engine blocks execution."""

    error: str = Field(..., description="Error classification category")
    detail: str = Field(..., description="Human-readable explanation of why safety check failed")
    blocked_by: str = Field(..., description="Identifier of blocking mechanism (kill_switch, caps, etc.)")


class ApplicationResponse(BaseModel):
    """Application record response."""

    id: UUID
    user_id: UUID
    job_id: UUID
    platform: str
    external_id: str
    profile_version: str
    autonomy_level: str
    status: str
    score: Optional[float] = None
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    approval_status: Optional[str] = None
    approved_at: Optional[str] = None
    idempotency_key: str
    evidence_ref: Optional[str] = None
    error: Optional[str] = None
    applied_at: Optional[str] = None
    created_at: str
    updated_at: str


class ApplicationEventResponse(BaseModel):
    """Audit event history record response."""

    id: UUID
    application_id: UUID
    event_type: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    reason: Optional[str] = None
    triggering_component: Optional[str] = None
    timestamp: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class ApplicationApprovalRequest(BaseModel):
    """Request payload for user application approval."""

    model_config = {"extra": "forbid"}
    user_id: UUID = Field(..., description="Owner user UUID approving the application")


class ApplicationRejectionRequest(BaseModel):
    """Request payload for user application rejection."""

    model_config = {"extra": "forbid"}
    user_id: UUID = Field(..., description="Owner user UUID rejecting the application")
    reason: str = Field(default="Rejected by user", max_length=200, description="Rejection rationale")


class PlannedFieldResponse(BaseModel):
    """Schema for individual planned field in a FillPlan."""

    field_id: str
    label: str
    input_type: str
    required: bool
    proposed_answer_ref: Optional[str] = None
    resolution_outcome: str
    policy_type: str
    field_category: str
    confidence: float
    explanation: str
    required_user_action: Optional[str] = None
    is_safe_to_prefill: bool


class FillPlanResponse(BaseModel):
    """Schema for complete Form FillPlan."""

    plan_id: UUID
    session_id: UUID
    job_id: Optional[UUID] = None
    canonical_url: str
    page_title: str
    total_fields: int
    auto_approved_count: int
    needs_review_count: int
    blocked_count: int
    unresolved_count: int
    is_executable: bool
    fields: List[PlannedFieldResponse] = Field(default_factory=list)
    created_at: str


class InspectionEvidenceResponse(BaseModel):
    """Schema for form inspection evidence metadata."""

    evidence_id: UUID
    session_id: UUID
    job_id: Optional[UUID] = None
    provider: str
    canonical_url: str
    page_title: str
    inspection_timestamp: str
    detected_field_count: int
    resolved_field_count: int
    unresolved_field_count: int
    blocked_field_count: int
    outcome: str
    screenshot_path: Optional[str] = None
    fill_plan_id: Optional[UUID] = None
    errors: List[str] = Field(default_factory=list)


class FormInspectionRequest(BaseModel):
    """Request schema for inspecting an application form and generating a FillPlan."""

    model_config = {"extra": "forbid"}

    user_id: UUID = Field(..., description="Owner user UUID initiating inspection")
    job_url_or_path: Optional[str] = Field(default=None, description="Target job fixture or URL to inspect")
    company: str = Field(default="Example Company", max_length=100)
    provider_name: str = Field(default="greenhouse", max_length=50)
