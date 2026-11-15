"""Deterministic idempotency key generation for applications.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 13, RC-3)
- migrations/001_initial_schema.sql (uq_applications_idempotency)
"""

from __future__ import annotations

import hashlib
from typing import Optional
from uuid import UUID


def generate_application_idempotency_key(
    user_id: UUID,
    job_id: UUID,
    profile_version: str,
    salt: Optional[str] = None,
) -> str:
    """Generate a deterministic, collision-resistant idempotency key bounded by 128 chars.

    Follows PostgreSQL constraint `uq_applications_idempotency VARCHAR(128)`.
    Format: `app_{sha256(user_id:job_id:profile_version[:salt])}`
    """
    raw_payload = f"{user_id}:{job_id}:{profile_version}"
    if salt:
        raw_payload += f":{salt}"

    digest = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()
    # Length: 4 + 64 = 68 characters, safely under 128 max
    return f"app_{digest}"
