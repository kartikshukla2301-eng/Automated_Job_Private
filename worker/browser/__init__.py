"""Playwright browser automation runtime and safe form execution foundation.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12)
- docs/BUILD_RULES.md
"""

from worker.browser.browser_config import BrowserConfig
from worker.browser.browser_manager import BrowserManager
from worker.browser.browser_session import BrowserSession, SessionLifecycleState
from worker.browser.evidence import EvidenceCollector, InspectionEvidence
from worker.browser.exceptions import (
    BrowserRuntimeError,
    EvidenceCaptureError,
    FormInspectionError,
    NavigationError,
    PrivateNetworkTargetError,
    SessionCancelledError,
    SessionError,
    SessionNotFoundError,
    SessionTimeoutError,
    UnsafeActionError,
    UnsupportedDestinationError,
)
from worker.browser.execution_context import ExecutionContext
from worker.browser.field_detector import DetectedField, is_sensitive_field
from worker.browser.fill_plan import FillPlan, PlannedField, ResolutionOutcome
from worker.browser.locator_resolver import LocatorResolver
from worker.browser.navigation_guard import NavigationGuard
from worker.browser.page_inspector import PageInspector

__all__ = [
    "BrowserConfig",
    "BrowserManager",
    "BrowserSession",
    "SessionLifecycleState",
    "EvidenceCollector",
    "InspectionEvidence",
    "BrowserRuntimeError",
    "EvidenceCaptureError",
    "FormInspectionError",
    "NavigationError",
    "PrivateNetworkTargetError",
    "SessionCancelledError",
    "SessionError",
    "SessionNotFoundError",
    "SessionTimeoutError",
    "UnsafeActionError",
    "UnsupportedDestinationError",
    "ExecutionContext",
    "DetectedField",
    "is_sensitive_field",
    "FillPlan",
    "PlannedField",
    "ResolutionOutcome",
    "LocatorResolver",
    "NavigationGuard",
    "PageInspector",
]
