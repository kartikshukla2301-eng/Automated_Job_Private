"""Centralized application and service configuration using Pydantic Settings."""

from typing import Dict, List, Literal, Optional
from fastapi import Request
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class AutonomyConfig(BaseModel):
    """Autonomy level configuration per provider and globally."""

    default_level: Literal["L0", "L1", "L2", "L3"] = "L0"
    per_provider: Dict[str, str] = Field(
        default_factory=lambda: {
            "greenhouse": "L0",
            "lever": "L0",
            "naukri": "L0",
            "linkedin": "L0",
        }
    )


class CapsConfig(BaseModel):
    """Application daily and monthly rate caps."""

    global_per_day: int = Field(default=20, ge=0)
    per_provider_per_day: Dict[str, int] = Field(
        default_factory=lambda: {
            "greenhouse": 15,
            "lever": 15,
            "naukri": 20,
            "linkedin": 10,
        }
    )
    per_company_per_30d: int = Field(default=1, ge=0)
    per_company_per_day: int = Field(default=2, ge=0)


class ScheduleConfig(BaseModel):
    """Scheduler timing and execution windows."""

    timezone: str = "Asia/Kolkata"
    active_hours: str = "09:00-23:00"
    delay_seconds: List[int] = Field(default_factory=lambda: [30, 90])


class MatchingConfig(BaseModel):
    """Job matching scoring and age limits."""

    threshold: int = Field(default=65, ge=0, le=100)
    borderline_band: List[int] = Field(default_factory=lambda: [55, 70])
    max_job_age_hours: int = Field(default=24, ge=1)


class LLMConfig(BaseModel):
    """LLM gateway quotas, circuit breaker thresholds, and model chains."""

    daily_call_budget: int = Field(default=400, ge=0)
    daily_cost_budget_usd: Optional[float] = Field(
        default=None, ge=0.0, description="Optional daily cost spending ceiling in USD"
    )
    chains: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            "unknown_question": ["model_a", "model_b"],
        }
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5, ge=1, description="Consecutive provider failures before opening circuit"
    )
    circuit_breaker_recovery_seconds: float = Field(
        default=60.0, ge=1.0, description="Seconds circuit stays OPEN before entering HALF_OPEN"
    )
    cache_ttl_seconds: int = Field(
        default=86400, ge=60, description="Default response cache expiration in seconds"
    )
    model_pricing: Dict[str, Dict[str, float]] = Field(
        default_factory=lambda: {
            "model_a": {
                "input_per_million": 0.20,
                "output_per_million": 0.20,
            },
            "model_b": {
                "input_per_million": 0.20,
                "output_per_million": 0.20,
            },
            "meta-llama/llama-3-8b-instruct": {
                "input_per_million": 0.20,
                "output_per_million": 0.20,
            },
        },
        description="Configured pricing fallback per 1M tokens: {'input_per_million': float, 'output_per_million': float}",
    )


class ApprovalConfig(BaseModel):
    """User approval queue expiry limits."""

    expire_hours: int = Field(default=24, ge=1)


class RetentionConfig(BaseModel):
    """Artifact and screenshot retention limits."""

    screenshots_days: int = Field(default=60, ge=1)


class ProfileConfig(BaseModel):
    """Candidate profile source and freshness settings."""

    source: Literal["local_file", "devleveler"] = "local_file"
    local_file_path: str = Field(default="fixtures/profile.yaml", description="Path to local profile YAML")
    stale_after_days: int = Field(default=7, ge=1)


class Settings(BaseSettings):
    """Central configuration for the AI Job Application Agent services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        yaml_file="config/config.yaml",
        yaml_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="AI Job Application Agent API", description="Service application name")
    app_env: Literal["development", "staging", "production", "test"] = Field(
        default="development", description="Service deployment environment"
    )
    app_version: str = Field(default="0.1.0", description="Semantic service version")
    debug: bool = Field(default=False, description="Enable FastAPI debug mode")

    api_host: str = Field(default="127.0.0.1", description="FastAPI host binding")
    api_port: int = Field(default=8000, ge=1, le=65535, description="FastAPI port binding")
    worker_token: Optional[str] = Field(
        default=None, description="Scoped worker API token for local control actions"
    )
    allow_tokenless_dev: bool = Field(
        default=False,
        description="Explicit flag permitting unauthenticated worker actions in development/test environments on localhost only",
    )
    real_submit_gate_enabled: bool = Field(
        default=False,
        description="Non-negotiable safety invariant: real form submissions are strictly disabled",
    )

    openrouter_api_key: Optional[str] = Field(
        default=None, description="OpenRouter API Key for runtime LLM gateway"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter base API endpoint"
    )
    openrouter_app_name: str = Field(
        default="AI Job Application Agent", description="HTTP-Referer/X-Title for OpenRouter"
    )
    openrouter_site_url: Optional[str] = Field(
        default="https://github.com/job-agent", description="OpenRouter site URL"
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Application log level"
    )

    autonomy: AutonomyConfig = Field(default_factory=AutonomyConfig)
    caps: CapsConfig = Field(default_factory=CapsConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    profile: ProfileConfig = Field(default_factory=ProfileConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


def get_settings(request: Request = None) -> Settings:
    """Factory function providing configured settings instance.

    When invoked within a FastAPI request context, resolves the settings
    bound to the current application state. Outside request contexts,
    returns a default Settings instance.
    """
    if request is not None and hasattr(request, "app") and hasattr(request.app.state, "settings"):
        return request.app.state.settings
    return Settings()


# Default singleton instance for application runtime
settings = get_settings()
