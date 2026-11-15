"""Data models and classification rules for detected application form fields.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 7, 8, 11)
- docs/BUILD_RULES.md
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


SENSITIVE_INPUT_TYPES = {
    "password",
    "file",
    "hidden",
    "submit",
    "button",
    "reset",
    "image",
}

SENSITIVE_KEYWORDS = (
    "password",
    "passwd",
    "otp",
    "one-time",
    "verification_code",
    "security_code",
    "mfa",
    "2fa",
    "captcha",
    "recaptcha",
    "hcaptcha",
    "turnstile",
    "ssn",
    "social security",
    "national_id",
    "passport",
    "driver_license",
    "driver's license",
    "bank_account",
    "routing_number",
    "iban",
    "swift",
    "credit_card",
    "cvv",
    "cvc",
)


class DetectedField(BaseModel):
    """Strongly typed normalized metadata of a form field detected on an application page."""

    model_config = ConfigDict(extra="forbid")

    field_id: str = Field(..., description="Deterministic unique identifier on the form")
    label: str = Field(..., description="Accessible human-readable label or description")
    name: Optional[str] = Field(default=None, description="HTML name attribute")
    html_id: Optional[str] = Field(default=None, description="HTML id attribute")
    tag_name: str = Field(default="input", description="HTML element tag (input, textarea, select)")
    input_type: str = Field(default="text", description="Normalized input type (text, email, tel, select, radio, etc.)")
    required: bool = Field(default=False, description="Whether the field is mandatory")
    placeholder: Optional[str] = Field(default=None, description="HTML placeholder text")
    options: List[str] = Field(default_factory=list, description="Available options for select, radio, or multi-choice")
    disabled: bool = Field(default=False, description="Whether the field is disabled")
    readonly: bool = Field(default=False, description="Whether the field is read-only")
    semantic_selector: str = Field(..., description="Robust semantic Playwright locator string")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence in field detection and locator validity")
    is_sensitive: bool = Field(default=False, description="Flagged true if field requires security/credential protection")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional DOM attributes or context")


def is_sensitive_field(label: str, name: Optional[str], html_id: Optional[str], input_type: str) -> bool:
    """Deterministically classify whether a field touches passwords, security codes, OTP, or government IDs."""
    if input_type.lower() in SENSITIVE_INPUT_TYPES:
        return True

    text_to_check = f"{label} {name or ''} {html_id or ''}".lower()
    for kw in SENSITIVE_KEYWORDS:
        if kw in text_to_check:
            return True

    return False
