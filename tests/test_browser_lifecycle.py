"""Tests for Playwright BrowserManager and BrowserSession lifecycle.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12)
- docs/BUILD_RULES.md
"""

from uuid import uuid4
import pytest

from worker.browser.browser_config import BrowserConfig
from worker.browser.browser_manager import BrowserManager
from worker.browser.browser_session import BrowserSession, SessionLifecycleState
from worker.browser.exceptions import SessionCancelledError, SessionError, SessionNotFoundError


@pytest.mark.asyncio
async def test_browser_manager_start_and_shutdown():
    """Verify BrowserManager starts Playwright, launches Chromium, and shuts down cleanly."""
    manager = BrowserManager(config=BrowserConfig(headless=True))
    assert manager.is_running is False

    await manager.start()
    assert manager.is_running is True

    await manager.shutdown()
    assert manager.is_running is False


@pytest.mark.asyncio
async def test_browser_session_isolation():
    """Verify separate users receive completely isolated contexts and sessions."""
    async with BrowserManager(config=BrowserConfig(headless=True)) as manager:
        user_1 = uuid4()
        user_2 = uuid4()

        sess_1 = await manager.create_session(user_id=user_1)
        sess_2 = await manager.create_session(user_id=user_2)

        assert sess_1.session_id != sess_2.session_id
        assert sess_1.user_id == user_1
        assert sess_2.user_id == user_2
        assert sess_1.context != sess_2.context
        assert sess_1.page != sess_2.page

        # Clean up
        await manager.close_session(sess_1.session_id)
        assert sess_1.state == SessionLifecycleState.CLOSED

        await manager.close_session(sess_2.session_id)
        assert sess_2.state == SessionLifecycleState.CLOSED


@pytest.mark.asyncio
async def test_browser_session_cancellation():
    """Verify cancelling a session aborts further page operations."""
    async with BrowserManager(config=BrowserConfig(headless=True)) as manager:
        user_id = uuid4()
        session = await manager.create_session(user_id=user_id)

        assert session.state == SessionLifecycleState.ACTIVE
        session.cancel(reason="User clicked cancel")

        assert session.is_cancelled is True
        assert session.state == SessionLifecycleState.CANCELLED

        with pytest.raises(SessionCancelledError):
            _ = session.page

        await session.close()


@pytest.mark.asyncio
async def test_close_nonexistent_session_raises_not_found():
    """Verify attempting to close an unknown session raises SessionNotFoundError."""
    async with BrowserManager(config=BrowserConfig(headless=True)) as manager:
        with pytest.raises(SessionNotFoundError):
            await manager.close_session(uuid4())


@pytest.mark.asyncio
async def test_session_cleanup_after_error():
    """Verify session resources are released cleanly when an operation fails."""
    async with BrowserManager(config=BrowserConfig(headless=True)) as manager:
        session = await manager.create_session(user_id=uuid4())
        page = session.page

        # Verify page is open
        assert not page.is_closed()

        # Close session
        await manager.close_session(session.session_id)

        # Page should now be closed
        assert session.state == SessionLifecycleState.CLOSED
        with pytest.raises(SessionError):
            session.ensure_active()
