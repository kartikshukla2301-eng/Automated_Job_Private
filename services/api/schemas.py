"""Pydantic schemas for FastAPI endpoints."""

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
