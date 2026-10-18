"""Tests for request correlation middleware and header handling."""

import re
from fastapi.testclient import TestClient

from services.api.main import app

client = TestClient(app)


def test_missing_request_id_generates_uuid():
    """Verify that omitting X-Request-ID results in a generated valid UUID header."""
    response = client.get("/health")
    assert response.status_code == 200
    req_id = response.headers.get("X-Request-ID")
    assert req_id is not None
    # Generated ID is 32-hex character UUID
    assert len(req_id) == 32
    assert re.match(r"^[0-9a-f]{32}$", req_id)


def test_valid_request_id_is_preserved():
    """Verify that a valid client-supplied X-Request-ID is echoed back."""
    valid_id = "client-trace-abc-123_456"
    response = client.get("/health", headers={"X-Request-ID": valid_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == valid_id


def test_invalid_request_id_is_rejected_and_replaced():
    """Verify that malicious or malformed request IDs are replaced with clean generated IDs."""
    malicious_ids = [
        "id with spaces and dangerous <script>",
        "id;DROP TABLE users;--",
        "a" * 100,  # exceeds 64 characters limit
        "invalid@#*&($",
    ]
    for bad_id in malicious_ids:
        response = client.get("/health", headers={"X-Request-ID": bad_id})
        assert response.status_code == 200
        echoed_id = response.headers.get("X-Request-ID")
        assert echoed_id != bad_id
        assert len(echoed_id) == 32
        assert re.match(r"^[0-9a-f]{32}$", echoed_id)
