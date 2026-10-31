"""Audit and traceability formatting for Answer Bank and policy decisions."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Keywords indicating sensitive answer values that must be redacted in audit logs
REDACTION_KEYWORDS = (
    "password",
    "secret",
    "ssn",
    "tax_id",
    "bank",
    "routing",
    "account",
    "salary",
    "compensation",
    "ctc",
    "credit_card",
    "token",
)


def redact_sensitive_value(key: str, value: Any) -> Any:
    """Redact sensitive answer values from audit logs."""
    if value is None:
        return None
    lower_key = key.lower()
    if any(kw in lower_key for kw in REDACTION_KEYWORDS):
        return "[REDACTED]"
    str_val = str(value)
    if len(str_val) > 100:
        return f"{str_val[:50]}...[TRUNCATED]"
    return value


def build_audit_metadata(
    field_key: str,
    resolution_method: str,
    policy_applied: str,
    result_status: str,
    reason: str,
    source: Optional[str] = None,
    entry_key: Optional[str] = None,
    raw_value: Optional[Any] = None,
) -> Dict[str, Any]:
    """Construct structured, sanitized audit metadata for resolution decisions.

    Guarantees:
    - Never logs unredacted sensitive values.
    - Captures method, status, policy, reason, and UTC timestamp.
    """
    return {
        "field_key": field_key,
        "entry_key": entry_key or field_key,
        "resolution_method": resolution_method,
        "policy_applied": policy_applied,
        "result_status": result_status,
        "reason": reason,
        "source": source or "unknown",
        "redacted_value": redact_sensitive_value(field_key, raw_value),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
