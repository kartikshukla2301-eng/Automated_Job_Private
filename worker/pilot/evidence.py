"""Evidence manager for L0 Pilot inspections with PII redaction (Phase 2.1).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger("worker.pilot.evidence")

# Sensitive PII patterns to sanitize before persisting evidence
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def sanitize_pii(text: str) -> str:
    """Sanitize PII in string content."""
    text = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    text = PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    text = SSN_PATTERN.sub("[REDACTED_SSN]", text)
    return text


def sanitize_dict_pii(data: Any) -> Any:
    """Recursively redact candidate PII and sensitive tokens from dictionaries and lists."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("password", "secret", "token", "auth", "cookie", "session", "api_key", "key")):
                sanitized[k] = "[REDACTED_SECRET]"
            elif isinstance(v, (dict, list)):
                sanitized[k] = sanitize_dict_pii(v)
            elif isinstance(v, str):
                sanitized[k] = sanitize_pii(v)
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(data, list):
        return [sanitize_dict_pii(item) for item in data]
    elif isinstance(data, str):
        return sanitize_pii(data)
    return data


class PilotEvidenceManager:
    """Manages secure, auditable, PII-sanitized evidence storage for L0 form inspections."""

    def __init__(self, base_evidence_dir: Optional[Path] = None) -> None:
        self.base_dir = base_evidence_dir or Path("worker/evidence/pilot")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store_evidence(
        self,
        record_id: UUID,
        user_id: UUID,
        provider: str,
        job_url: str,
        schema_snapshot: List[Dict[str, Any]],
        fill_plan: Dict[str, Any],
        policy_decisions: Dict[str, Any],
        screenshot_bytes: Optional[bytes] = None,
    ) -> Path:
        """Persist structured evidence bundle for a pilot inspection record."""
        target_dir = self.base_dir / str(record_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. Sanitize schema and plan
        sanitized_schema = sanitize_dict_pii(schema_snapshot)
        sanitized_plan = sanitize_dict_pii(fill_plan)
        sanitized_policies = sanitize_dict_pii(policy_decisions)

        # 2. Save JSON artifacts
        (target_dir / "form_schema.json").write_text(
            json.dumps(sanitized_schema, indent=2, default=str), encoding="utf-8"
        )
        (target_dir / "fill_plan.json").write_text(
            json.dumps(sanitized_plan, indent=2, default=str), encoding="utf-8"
        )
        (target_dir / "policy_decisions.json").write_text(
            json.dumps(sanitized_policies, indent=2, default=str), encoding="utf-8"
        )

        # 3. Calculate provenance audit hash
        hasher = hashlib.sha256()
        hasher.update(json.dumps(sanitized_schema, sort_keys=True, default=str).encode("utf-8"))
        hasher.update(json.dumps(sanitized_plan, sort_keys=True, default=str).encode("utf-8"))
        audit_hash = hasher.hexdigest()

        # 4. Save metadata summary
        metadata = {
            "record_id": str(record_id),
            "user_id": str(user_id),
            "provider": provider,
            "job_url": job_url,
            "audit_hash": audit_hash,
            "fields_count": len(schema_snapshot),
            "timestamp": target_dir.stat().st_mtime,
        }
        (target_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

        # 5. Save screenshot if present
        if screenshot_bytes:
            (target_dir / "screenshot.png").write_bytes(screenshot_bytes)

        return target_dir

    def get_evidence(self, record_id: UUID) -> Optional[Dict[str, Any]]:
        """Retrieve stored evidence package metadata."""
        target_dir = self.base_dir / str(record_id)
        meta_file = target_dir / "metadata.json"
        if not meta_file.exists():
            return None
        try:
            return json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to load evidence metadata for record %s: %s", record_id, e)
            return None
