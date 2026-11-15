"""Configuration models for isolated Playwright browser sessions.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12)
- docs/BUILD_RULES.md
"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BrowserConfig(BaseModel):
    """Configuration settings for Playwright browser and session isolation."""

    model_config = ConfigDict(extra="forbid")

    headless: bool = Field(default=True, description="Whether to launch browser in headless mode")
    slow_mo_ms: int = Field(default=0, ge=0, le=5000, description="Milliseconds to slow down execution for debugging")
    default_timeout_ms: int = Field(default=30000, ge=1000, le=120000, description="Default timeout for page operations")
    navigation_timeout_ms: int = Field(default=30000, ge=1000, le=120000, description="Timeout for page navigation")
    screenshot_timeout_ms: int = Field(default=10000, ge=1000, le=30000, description="Timeout for evidence screenshot capture")
    viewport_width: int = Field(default=1280, ge=800, le=3840, description="Browser viewport width in pixels")
    viewport_height: int = Field(default=800, ge=600, le=2160, description="Browser viewport height in pixels")
    user_agent: Optional[str] = Field(default=None, description="Custom User-Agent header string")
    
    # Strictly locked supported provider origins
    allowed_domains: List[str] = Field(
        default_factory=lambda: [
            "boards.greenhouse.io",
            "job-boards.greenhouse.io",
            "jobs.lever.co",
            "naukri.com",
            "www.naukri.com",
        ],
        description="Explicit list of approved job board application domains",
    )
