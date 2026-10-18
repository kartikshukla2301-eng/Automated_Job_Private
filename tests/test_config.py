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


def test_yaml_config_loading():
    """Verify that configuration parses values from config/config.yaml."""
    s = Settings()
    # Values defined in config/config.yaml
    assert s.autonomy.default_level == "L0"
    assert s.autonomy.per_provider["greenhouse"] == "L0"
    assert s.caps.global_per_day == 20
    assert s.caps.per_provider_per_day["greenhouse"] == 15
    assert s.schedule.timezone == "Asia/Kolkata"
    assert s.matching.threshold == 65
    assert s.profile.source == "local_file"


def test_precedence_env_overrides_yaml(monkeypatch):
    """Verify environment variable overrides YAML configuration values."""
    monkeypatch.setenv("AUTONOMY__DEFAULT_LEVEL", "L1")
    s = Settings()
    assert s.autonomy.default_level == "L1"


def test_precedence_init_overrides_env_and_yaml(monkeypatch):
    """Verify explicit constructor argument overrides both env vars and YAML."""
    from services.api.config import AutonomyConfig

    monkeypatch.setenv("AUTONOMY__DEFAULT_LEVEL", "L1")
    s = Settings(autonomy=AutonomyConfig(default_level="L2"))
    assert s.autonomy.default_level == "L2"


def test_port_out_of_bounds():
    """Verify port bound validation fails for out-of-range port numbers."""
    with pytest.raises(ValidationError):
        Settings(api_port=70000)

    with pytest.raises(ValidationError):
        Settings(api_port=0)


def test_matching_threshold_bounds():
    """Verify matching threshold bound validation enforces 0-100 scale."""
    from services.api.config import MatchingConfig

    with pytest.raises(ValidationError):
        MatchingConfig(threshold=101)

    with pytest.raises(ValidationError):
        MatchingConfig(threshold=-1)

