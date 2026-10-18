"""Tests for structured logging, JSON formatting, and secret redaction."""

import json
import logging
from datetime import datetime

from services.api.logging_config import (
    JSONFormatter,
    RedactionFilter,
    redact_sensitive_data,
    request_id_ctx,
    setup_logging,
)


def test_redact_sensitive_dict_keys():
    """Verify recursive redaction of sensitive dictionary keys."""
    raw = {
        "username": "kartik",
        "password": "supersecretpassword",
        "api_key": "sk-test-12345",
        "token": "bearer-xyz",
        "nested": {
            "secret_value": "hidden",
            "safe_value": "visible",
        },
    }
    redacted = redact_sensitive_data(raw)
    assert redacted["username"] == "kartik"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["nested"]["secret_value"] == "[REDACTED]"
    assert redacted["nested"]["safe_value"] == "visible"


def test_redact_sensitive_patterns_in_strings():
    """Verify regex pattern redaction for Bearer tokens and key strings."""
    msg = "Connecting with Bearer sk-or-v1-abcdef123456 and api_key=topsecret"
    redacted = redact_sensitive_data(msg)
    assert "sk-or-v1-abcdef123456" not in redacted
    assert "topsecret" not in redacted
    assert "Bearer [REDACTED]" in redacted
    assert "api_key=[REDACTED]" in redacted


def test_json_formatter_structure():
    """Verify JSONFormatter produces valid structured JSON with required fields."""
    formatter = JSONFormatter(service_name="test-service")
    logger = logging.getLogger("test_formatter_logger")
    record = logger.makeRecord(
        name="test_formatter_logger",
        level=logging.INFO,
        fn="test_fn",
        lno=42,
        msg="Test event message",
        args=(),
        exc_info=None,
    )

    request_id_ctx.set("corr-999")
    try:
        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["service"] == "test-service"
        assert data["logger"] == "test_formatter_logger"
        assert data["message"] == "Test event message"
        assert data["request_id"] == "corr-999"

        # Verify timestamp is valid UTC ISO format
        ts = datetime.fromisoformat(data["timestamp"])
        assert ts.tzinfo is not None
    finally:
        request_id_ctx.set(None)


def test_setup_logging_idempotence():
    """Verify setup_logging does not add duplicate handlers on multiple calls."""
    root_logger = logging.getLogger()
    setup_logging(service_name="job-agent-api", log_level="INFO")
    handler_count_1 = len(root_logger.handlers)

    # Call setup_logging second time
    setup_logging(service_name="job-agent-api", log_level="INFO")
    handler_count_2 = len(root_logger.handlers)

    assert handler_count_1 == 1
    assert handler_count_2 == 1
