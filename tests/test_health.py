"""Tests for GET /health endpoint."""

from fastapi.testclient import TestClient

from services.api.main import app
from services.api.schemas import HealthResponse

client = TestClient(app)


def test_health_endpoint_returns_200():
    """Verify health check returns HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_matches_schema():
    """Verify response payload satisfies HealthResponse model."""
    response = client.get("/health")
    data = response.json()
    validated = HealthResponse.model_validate(data)
    assert validated.status == "healthy"
    assert validated.service == "job-agent-api"
    assert validated.version == "0.1.0"
    assert validated.environment in ["development", "staging", "production", "test"]


def test_health_endpoint_does_not_expose_secrets_or_paths():
    """Verify response does not leak sensitive keys, paths, or credentials."""
    response = client.get("/health")
    data = response.json()
    expected_keys = {"status", "service", "version", "environment"}
    assert set(data.keys()) == expected_keys
    # Ensure sensitive terms are absent from all values
    text_content = str(data).lower()
    for sensitive in ["key", "secret", "token", "password", "supabase", "openrouter", "path", "c:\\"]:
        assert sensitive not in text_content
