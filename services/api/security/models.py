"""Security models and role taxonomy for API authorization (Phase 2.3).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    OWNER = "OWNER"
    OPERATOR = "OPERATOR"
    WORKER = "WORKER"
    ADMIN = "ADMIN"


class AuthenticatedSubject(BaseModel):
    """Authenticated entity (human user, operator, or backend worker)."""

    model_config = ConfigDict(extra="forbid")

    subject_id: UUID = Field(..., description="Unique entity UUID")
    role: UserRole = Field(..., description="Role category (OWNER, OPERATOR, WORKER, ADMIN)")
    email: Optional[str] = Field(default=None, description="Candidate or operator email")
    token_type: str = Field(default="user_jwt", description="Type of token presented (worker_token, user_jwt, dev_local)")
    is_authenticated: bool = Field(default=True)
