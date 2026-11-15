"""Isolated browser session wrapper managing Playwright contexts and pages.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12)
- docs/BUILD_RULES.md
"""

import asyncio
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Optional
from uuid import UUID, uuid4

from worker.browser.exceptions import SessionCancelledError, SessionError

logger = logging.getLogger("worker.browser.session")


class SessionLifecycleState(str, Enum):
    """Lifecycle state of an isolated browser session."""

    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    INSPECTING = "INSPECTING"
    CLOSED = "CLOSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BrowserSession:
    """Manages an isolated Playwright BrowserContext and Page for a single user operation.

    SECURITY & CONCURRENCY INVARIANTS:
    - Per-user session isolation: sessions are NEVER shared between users.
    - Ephemeral: no persistent browser profile, cookies, or credentials survive session close.
    - Cancellation aware: cancellation flags abort in-flight inspections immediately.
    """

    def __init__(
        self,
        user_id: UUID,
        session_id: Optional[UUID] = None,
        timeout_ms: int = 30000,
    ) -> None:
        self.session_id: UUID = session_id or uuid4()
        self.user_id: UUID = user_id
        self.timeout_ms: int = timeout_ms
        self.state: SessionLifecycleState = SessionLifecycleState.INITIALIZING
        self.created_at: datetime = datetime.now(timezone.utc)
        self.closed_at: Optional[datetime] = None

        self._browser_context: Optional[Any] = None
        self._page: Optional[Any] = None
        self._cancellation_requested: bool = False
        self._cancellation_reason: Optional[str] = None
        self._lock = asyncio.Lock()

    @property
    def page(self) -> Any:
        self.ensure_active()
        return self._page

    @property
    def context(self) -> Any:
        self.ensure_active()
        return self._browser_context

    @property
    def is_cancelled(self) -> bool:
        return self._cancellation_requested

    def attach_playwright_handles(self, context: Any, page: Any) -> None:
        """Attach underlying Playwright BrowserContext and Page instances."""
        self._browser_context = context
        self._page = page
        self.state = SessionLifecycleState.ACTIVE

    def ensure_active(self) -> None:
        """Verify the session is in an operable state."""
        if self._cancellation_requested:
            raise SessionCancelledError(
                str(self.session_id),
                self._cancellation_reason or "Cancellation requested",
            )
        if self.state in (SessionLifecycleState.CLOSED, SessionLifecycleState.FAILED, SessionLifecycleState.CANCELLED):
            raise SessionError(f"Session '{self.session_id}' is not active (state: {self.state.value}).")

    def cancel(self, reason: str = "User or orchestrator interrupt") -> None:
        """Mark the session as cancelled to halt ongoing or upcoming operations."""
        self._cancellation_requested = True
        self._cancellation_reason = reason
        self.state = SessionLifecycleState.CANCELLED
        logger.info("BrowserSession %s cancelled: %s", self.session_id, reason)

    async def close(self) -> None:
        """Clean up Playwright page and context resources safely."""
        async with self._lock:
            if self.state == SessionLifecycleState.CLOSED:
                return

            try:
                if self._page and not self._page.is_closed():
                    await self._page.close()
            except Exception as exc:
                logger.debug("Error closing page in session %s: %s", self.session_id, exc)
            finally:
                self._page = None

            try:
                if self._browser_context:
                    await self._browser_context.close()
            except Exception as exc:
                logger.debug("Error closing context in session %s: %s", self.session_id, exc)
            finally:
                self._browser_context = None

            if self.state != SessionLifecycleState.CANCELLED:
                self.state = SessionLifecycleState.CLOSED
            self.closed_at = datetime.now(timezone.utc)
            logger.debug("BrowserSession %s closed cleanly.", self.session_id)
