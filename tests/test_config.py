"""Tests for API configuration and validation."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from services.api.config import Settings
from services.api.main import create_app


def test_default_settings():
    """Verify standard default configuration."""
    s = Settings()
    assert s.app_name == "AI Job Application Agent API"
    assert s.app_env == "development"
    assert s.api_port == 8000
    assert s.debug is False


def test_custom_settings_injection():
    """Verify dependency injection of custom settings into app factory."""
    custom = Settings(app_env="test", app_version="0.2.0")
    custom_app = create_app(custom)
    client = TestClient(custom_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["environment"] == "test"
    assert response.json()["version"] == "0.2.0"


def test_invalid_configuration_types():
    """Verify validation error when port is non-numeric."""
    with pytest.raises(ValidationError):
        Settings(api_port="invalid_port_string")
