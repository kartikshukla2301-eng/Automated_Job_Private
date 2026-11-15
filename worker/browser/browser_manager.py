"""Central Playwright BrowserManager controlling browser lifecycle and session allocation.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12)
- docs/BUILD_RULES.md
"""

import asyncio
import logging
from typing import Dict, Optional
from uuid import UUID

from playwright.async_api import Browser, Playwright, async_playwright

from worker.browser.browser_config import BrowserConfig
from worker.browser.browser_session import BrowserSession
from worker.browser.exceptions import BrowserRuntimeError, SessionNotFoundError

logger = logging.getLogger("worker.browser.manager")


class BrowserManager:
    """Manages Playwright process lifecycle and dispenses isolated BrowserSessions."""

    def __init__(self, config: Optional[BrowserConfig] = None) -> None:
        self.config = config or BrowserConfig()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._sessions: Dict[UUID, BrowserSession] = {}
        self._lock = asyncio.Lock()
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def start(self) -> None:
        """Start Playwright runtime and launch the Chromium browser."""
        async with self._lock:
            if self._is_running:
                return

            logger.info("Starting BrowserManager (headless=%s)...", self.config.headless)
            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=self.config.headless,
                    slow_mo=self.config.slow_mo_ms,
                )
                self._is_running = True
                logger.info("BrowserManager started successfully.")
            except Exception as exc:
                self._is_running = False
                await self._cleanup_handles()
                raise BrowserRuntimeError(f"Failed to launch browser: {exc}") from exc

    async def create_session(
        self,
        user_id: UUID,
        session_id: Optional[UUID] = None,
        custom_config: Optional[BrowserConfig] = None,
    ) -> BrowserSession:
        """Allocate and initialize a new isolated BrowserSession."""
        if not self._is_running:
            await self.start()

        cfg = custom_config or self.config
        session = BrowserSession(
            user_id=user_id,
            session_id=session_id,
            timeout_ms=cfg.default_timeout_ms,
        )

        async with self._lock:
            if not self._browser or not self._browser.is_connected():
                raise BrowserRuntimeError("Underlying Playwright browser is not connected.")

            # Create an isolated, incognito browser context
            context_kwargs = {
                "viewport": {
                    "width": cfg.viewport_width,
                    "height": cfg.viewport_height,
                },
                "accept_downloads": False,  # Strict L0: no file downloads
            }
            if cfg.user_agent:
                context_kwargs["user_agent"] = cfg.user_agent

            context = await self._browser.new_context(**context_kwargs)
            context.set_default_timeout(cfg.default_timeout_ms)
            context.set_default_navigation_timeout(cfg.navigation_timeout_ms)

            page = await context.new_page()
            session.attach_playwright_handles(context=context, page=page)
            self._sessions[session.session_id] = session

        logger.debug("Created BrowserSession %s for user %s", session.session_id, user_id)
        return session

    async def get_session(self, session_id: UUID) -> Optional[BrowserSession]:
        """Retrieve active session by UUID."""
        async with self._lock:
            return self._sessions.get(session_id)

    async def close_session(self, session_id: UUID) -> None:
        """Close an active session and release its browser context."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)

        if session:
            await session.close()
        else:
            raise SessionNotFoundError(str(session_id))

    async def shutdown(self) -> None:
        """Shutdown all active sessions, close browser, and stop Playwright."""
        async with self._lock:
            logger.info("Shutting down BrowserManager...")
            # Close all active sessions
            active_sessions = list(self._sessions.values())
            self._sessions.clear()

        for sess in active_sessions:
            try:
                await sess.close()
            except Exception as exc:
                logger.debug("Error closing session during shutdown: %s", exc)

        async with self._lock:
            await self._cleanup_handles()
            self._is_running = False
            logger.info("BrowserManager shutdown complete.")

    async def _cleanup_handles(self) -> None:
        if self._browser:
            try:
                await self._browser.close()
            except Exception as exc:
                logger.debug("Error closing browser handle: %s", exc)
            finally:
                self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as exc:
                logger.debug("Error stopping Playwright handle: %s", exc)
            finally:
                self._playwright = None

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()
