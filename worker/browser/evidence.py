"""Structured evidence capture for browser form inspection.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12, 13)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("worker.browser.evidence")


class InspectionEvidence(BaseModel):
    """Immutable audit record capturing form inspection telemetry and screenshot reference.

    SAFETY & INTEGRITY RULES:
    - Never stores raw candidate credentials, tokens, passwords, or OTP values.
    - Screenshot path references safe storage artifacts within worker/sessions/evidence/.
    - Does not dump cookies, session storage, or authorization tokens.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID = Field(default_factory=uuid4, description="Unique evidence record identifier")
    session_id: UUID = Field(..., description="Browser session UUID")
    job_id: Optional[UUID] = Field(default=None, description="Target job UUID if applicable")
    provider: str = Field(default="greenhouse", description="Target provider (greenhouse, lever)")
    canonical_url: str = Field(..., description="Target application URL")
    page_title: str = Field(default="", description="Application page title")
    inspection_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when inspection occurred",
    )
    detected_field_count: int = Field(default=0, ge=0)
    resolved_field_count: int = Field(default=0, ge=0)
    unresolved_field_count: int = Field(default=0, ge=0)
    blocked_field_count: int = Field(default=0, ge=0)
    outcome: str = Field(default="INSPECTION_COMPLETED", description="Outcome label")
    screenshot_path: Optional[str] = Field(
        default=None,
        description="Relative path to captured full-page form screenshot",
    )
    fill_plan_id: Optional[UUID] = Field(default=None, description="Linked FillPlan UUID")
    errors: List[str] = Field(default_factory=list, description="Sanitized error notices if any")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Sanitized inspection metrics")


class EvidenceCollector:
    """Manages secure artifact storage and evidence record creation."""

    def __init__(self, evidence_dir: Optional[Path] = None) -> None:
        self.evidence_dir = evidence_dir or Path("worker/sessions/evidence")
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    async def capture_screenshot(
        self,
        page: Any,
        session_id: UUID,
        prefix: str = "form_inspection",
    ) -> Optional[str]:
        """Capture full-page screenshot of the inspected form into evidence storage."""
        try:
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{session_id}_{timestamp_str}.png"
            target_path = self.evidence_dir / filename

            await page.screenshot(path=str(target_path), full_page=True)
            logger.debug("Captured evidence screenshot at %s", target_path)
            # Return relative POSIX path for portability
            return target_path.as_posix()
        except Exception as exc:
            logger.warning("Failed to capture evidence screenshot: %s", exc)
            return None
