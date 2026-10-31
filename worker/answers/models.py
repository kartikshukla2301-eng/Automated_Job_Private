"""Strongly typed models for Answer Bank entries and resolution results.

Following Section 7 of docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx:
- Provenance and freshness tracking for every answer record.
- Strict validation: reject malformed or unsupported entries.
- Never invent candidate facts.
- Expired or needs_review answers must not be treated as verified.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from worker.policy.taxonomy import PolicyType


class AnswerType(str, Enum):
    """Supported field answer types aligning with the locked database schema."""

    TEXT = "text"
    SELECT = "select"
    BOOLEAN = "boolean"
    NUMBER = "number"
    DATE = "date"
    TEXTAREA = "textarea"


class AnswerSource(str, Enum):
    """Source provenance of the answer record."""

    USER = "user"
    PROFILE = "profile"
    RESUME = "resume"
    LLM = "llm"


class ResolutionStatus(str, Enum):
    """Typed resolution outcomes for form field resolution."""

    RESOLVED = "RESOLVED"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    EXPIRED = "EXPIRED"
    AMBIGUOUS = "AMBIGUOUS"
    NO_MATCH = "NO_MATCH"
    POLICY_BLOCKED = "POLICY_BLOCKED"


class AnswerBankEntry(BaseModel):
    """Strongly typed Answer Bank entry with provenance and freshness."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., min_length=1, description="Unique normalized answer key (e.g. notice_period_days)")
    category: str = Field(..., min_length=1, description="Taxonomy category name")
    aliases: List[str] = Field(default_factory=list, description="Alternative field names or labels")
    variants: List[str] = Field(default_factory=list, description="Question phrasing variants")
    type: AnswerType = Field(default=AnswerType.TEXT, description="Expected value type")
    value: Any = Field(..., description="Canonical answer value")
    option_mapping: Dict[str, str] = Field(
        default_factory=dict,
        description="Option mapping for select/radio dropdown choices",
    )
    scope: str = Field(default="global", description="Scope: global, company:<name>, or provider:<name>")
    policy: PolicyType = Field(default=PolicyType.ALWAYS_ASK, description="Field filling policy")
    source: AnswerSource = Field(default=AnswerSource.USER, description="Provenance source of the answer")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    needs_review: bool = Field(default=False, description="Flag indicating whether manual review is required")
    last_confirmed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the user last verified this answer",
    )
    valid_until: Optional[datetime] = Field(
        default=None,
        description="Expiration timestamp past which the answer is stale",
    )
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Optional vector embedding representation",
    )

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean:
            raise ValueError("Answer key cannot be empty or whitespace.")
        return clean

    @field_validator("aliases", "variants")
    @classmethod
    def clean_string_list(cls, items: List[str]) -> List[str]:
        cleaned: List[str] = []
        for item in items:
            s = item.strip()
            if s and s not in cleaned:
                cleaned.append(s)
        return cleaned

    @model_validator(mode="after")
    def enforce_architectural_rules(self) -> "AnswerBankEntry":
        # Rule from Section 7: source == llm always sets needs_review = True
        if self.source == AnswerSource.LLM and not self.needs_review:
            # Enforce needs_review for LLM sourced records
            object.__setattr__(self, "needs_review", True)

        # Ensure valid_until is after last_confirmed_at if specified
        if self.valid_until and self.valid_until < self.last_confirmed_at:
            raise ValueError("valid_until cannot be earlier than last_confirmed_at")

        # Type-specific validation for value
        val = self.value
        if self.type == AnswerType.NUMBER:
            try:
                float(val)
            except (ValueError, TypeError):
                raise ValueError(f"Value '{val}' cannot be parsed as a number for type '{self.type.value}'")
        elif self.type == AnswerType.BOOLEAN:
            if not isinstance(val, bool):
                if str(val).lower() not in ("true", "false", "yes", "no", "1", "0"):
                    raise ValueError(f"Value '{val}' cannot be parsed as a boolean for type '{self.type.value}'")

        return self

    def is_expired(self, as_of: Optional[datetime] = None) -> bool:
        """Check if this record is past its validity expiration timestamp."""
        if self.valid_until is None:
            return False
        reference_time = as_of or datetime.now(timezone.utc)
        if self.valid_until.tzinfo is None:
            target = self.valid_until.replace(tzinfo=timezone.utc)
        else:
            target = self.valid_until
        return reference_time > target

    def is_verified(self, as_of: Optional[datetime] = None) -> bool:
        """Return True if the answer is active, unexpired, and not flagged for review."""
        if self.needs_review:
            return False
        if self.is_expired(as_of):
            return False
        return True


class FieldResolutionResult(BaseModel):
    """Auditable resolution result for a single form field."""

    model_config = ConfigDict(extra="forbid")

    status: ResolutionStatus
    field_key: str
    resolved_value: Optional[Any] = None
    applied_option: Optional[str] = None
    entry: Optional[AnswerBankEntry] = None
    policy: PolicyType = PolicyType.ALWAYS_ASK
    policy_approved: bool = False
    reason: str = ""
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)
