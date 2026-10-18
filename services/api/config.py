"""FastAPI service configuration using Pydantic Settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable fallback and validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="AI Job Application Agent API", description="Service application name")
    app_env: str = Field(default="development", description="Environment: development, staging, production")
    app_version: str = Field(default="0.1.0", description="Service semantic version")
    debug: bool = Field(default=False, description="Enable FastAPI debug mode")

    api_host: str = Field(default="127.0.0.1", description="FastAPI bind host")
    api_port: int = Field(default=8000, description="FastAPI bind port")


settings = Settings()
