"""Base contracts and models for job provider adapters."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from worker.profile.models import ProfileSnapshot


class FormField(BaseModel):
    """Inspected form field metadata."""

    field_id: str = Field(..., description="DOM ID or unique locator for the field")
    name: Optional[str] = Field(default=None, description="HTML input name attribute")
    label: str = Field(..., description="Human-readable field label or associated question text")
    field_type: str = Field(default="text", description="HTML input type (text, email, tel, textarea, select, file)")
    required: bool = Field(default=False, description="Whether the field is marked required in the form")
    resolved_value: Optional[str] = Field(default=None, description="Value resolved from profile, or None if unresolved")
    is_resolved: bool = Field(default=False, description="True if value was resolved truthfully from profile")


class FormFillResult(BaseModel):
    """Result of inspecting and performing dry-run fill on a job application form."""

    provider: str = Field(..., description="Provider identifier (e.g. greenhouse, lever)")
    fields_filled: Dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary mapping field labels/names to the values filled",
    )
    unresolved_fields: List[str] = Field(
        default_factory=list,
        description="List of required or custom fields that could not be resolved from profile",
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
    """Protocol implemented by platform-specific job board adapters."""

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
