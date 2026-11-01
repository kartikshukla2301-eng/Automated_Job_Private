"""Base contracts and models for job provider adapters and form inspection.

Following Architecture v1.0 LOCKED and Phase 1.1 Requirements:
- Strongly typed FormField metadata with taxonomy classification and policy status.
- Integration with AnswerResolver and PolicyEngine.
- JobDiscoveryAdapter protocol for public board ingestion.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel, ConfigDict, Field

from worker.answers.models import ResolutionStatus
from worker.policy.taxonomy import FieldCategory, PolicyType
from worker.profile.models import ProfileSnapshot

if TYPE_CHECKING:
    from worker.discovery.models import Job


class FormField(BaseModel):
    """Inspected form field metadata with classification and resolution status."""

    model_config = ConfigDict(extra="forbid")

    field_id: str = Field(..., description="DOM ID or unique locator for the field")
    name: Optional[str] = Field(default=None, description="HTML input name attribute")
    label: str = Field(..., description="Human-readable field label or associated question text")
    field_type: str = Field(
        default="text",
        description="HTML input type (text, email, tel, textarea, select, radio, checkbox, file)",
    )
    required: bool = Field(default=False, description="Whether the field is marked required in the form")
    options: List[str] = Field(
        default_factory=list,
        description="Available options for select, radio, or checkbox choices",
    )
    classification: Optional[FieldCategory] = Field(
        default=None,
        description="PolicyEngine taxonomy classification",
    )
    policy: PolicyType = Field(
        default=PolicyType.ALWAYS_ASK,
        description="Evaluated policy rule (auto, auto+log, always_ask, never_fill)",
    )
    resolution_status: ResolutionStatus = Field(
        default=ResolutionStatus.NO_MATCH,
        description="Resolution status from AnswerResolver or profile lookup",
    )
    resolved_value: Optional[Any] = Field(
        default=None,
        description="Resolved candidate answer value, or None if unresolved",
    )
    applied_option: Optional[str] = Field(
        default=None,
        description="Mapped choice option string if dropdown or radio",
    )
    is_resolved: bool = Field(
        default=False,
        description="True if value was resolved truthfully from profile or answer bank",
    )
    policy_approved: bool = Field(
        default=False,
        description="True only if PolicyEngine explicitly approves automated filling",
    )
    reason: str = Field(
        default="",
        description="Diagnostic explanation for resolution outcome or policy decision",
    )
    audit_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Audit and provenance metadata with sensitive values redacted",
    )


class FormFillResult(BaseModel):
    """Result of inspecting and performing dry-run fill on a job application form."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(..., description="Provider identifier (e.g. greenhouse, lever)")
    fields_filled: Dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary mapping field labels/names to the values filled",
    )
    unresolved_fields: List[str] = Field(
        default_factory=list,
        description="List of required or custom fields that could not be resolved from profile",
    )
    discovered_fields: List[FormField] = Field(
        default_factory=list,
        description="Complete list of all discovered and classified form fields",
    )
    screenshot_path: Optional[str] = Field(
        default=None,
        description="Filesystem path to captured evidence screenshot",
    )
    submit_attempted: bool = Field(
        default=False,
        description="Whether a submit action was attempted (strictly False in dry-run)",
    )
    success: bool = Field(
        default=True,
        description="Whether the inspection and dry-run filling completed without fatal error",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if form inspection or filling failed",
    )


@runtime_checkable
class JobProvider(Protocol):
    """Protocol implemented by platform-specific job application form adapters."""

    name: str

    async def inspect_and_fill(
        self,
        page: Any,
        profile: ProfileSnapshot,
        dry_run: bool = True,
        screenshot_dir: Optional[Path] = None,
    ) -> FormFillResult:
        """Inspect the open application form and perform dry-run filling without submitting."""
        ...


@runtime_checkable
class JobDiscoveryAdapter(Protocol):
    """Protocol implemented by platform-specific job discovery adapters."""

    name: str

    async def fetch_jobs(
        self,
        company: str,
        client: Optional[httpx.AsyncClient] = None,
        **kwargs: Any,
    ) -> List[Job]:
        """Fetch and normalize job postings for a company board."""
        ...
