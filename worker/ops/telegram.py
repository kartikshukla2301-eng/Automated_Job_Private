"""Telegram Notification and Owner Command Adapter (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Appendix B)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import UUID

from worker.application.models import Application, ApplicationStatus
from worker.ops.approval import ApprovalManager

logger = logging.getLogger(__name__)


class TelegramSecurityError(Exception):
    """Raised when an unauthorized Telegram user or chat attempts an operation."""


class TelegramNotifier:
    """Interface / protocol for sending notifications."""

    async def send_message(self, text: str, chat_id: Optional[int] = None) -> bool:
        raise NotImplementedError


class MockTelegramNotifier(TelegramNotifier):
    """Mock notifier for testing or when live Telegram credentials are unconfigured."""

    def __init__(self) -> None:
        self.sent_messages: List[Dict[str, Any]] = []

    async def send_message(self, text: str, chat_id: Optional[int] = None) -> bool:
        self.sent_messages.append({"text": text, "chat_id": chat_id, "sent_at": datetime.now(timezone.utc)})
        logger.info("[MockTelegram] Sent notification: %s (chat_id=%s)", text[:100], chat_id)
        return True


class TelegramNotificationService:
    """Central operational notification and command handling service via Telegram."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        allowed_chat_ids: Optional[List[int]] = None,
        notifier: Optional[TelegramNotifier] = None,
        approval_manager: Optional[ApprovalManager] = None,
        kill_switch: Optional[Any] = None,
        provider_health_mgr: Optional[Any] = None,
    ) -> None:
        self.bot_token = bot_token
        self.allowed_chat_ids: Set[int] = set(allowed_chat_ids or [])
        self.is_live_configured = bool(bot_token and self.allowed_chat_ids)
        self.notifier = notifier or MockTelegramNotifier()
        self.approval_manager = approval_manager
        self.kill_switch = kill_switch
        self.provider_health_mgr = provider_health_mgr

    # -------------------------------------------------------------------------
    # Outbound Notifications (Never expose raw PII or credentials)
    # -------------------------------------------------------------------------

    async def notify_approval_requested(
        self,
        application_id: UUID,
        company: str,
        title: str,
        match_score: Optional[float] = None,
        chat_id: Optional[int] = None,
    ) -> bool:
        """Alert owner of an application queued in AWAITING_APPROVAL."""
        score_str = f" | Match: {match_score:.1f}%" if match_score is not None else ""
        msg = (
            f"🔔 *Job Application Approval Required*\n"
            f"• *Company*: {company}\n"
            f"• *Title*: {title}{score_str}\n"
            f"• *App ID*: `{application_id}`\n\n"
            f"Reply with `/approve {application_id}` or `/reject {application_id} <reason>`."
        )
        return await self._dispatch_alert(msg, chat_id)

    async def notify_needs_user_input(
        self,
        application_id: UUID,
        missing_fields: List[str],
        chat_id: Optional[int] = None,
    ) -> bool:
        """Alert owner that an application requires user answers."""
        field_list = ", ".join(missing_fields[:5])
        msg = (
            f"❓ *Candidate Input Needed*\n"
            f"Application `{application_id}` requires missing answers:\n"
            f"• Fields: {field_list}\n"
            f"Please review in web dashboard."
        )
        return await self._dispatch_alert(msg, chat_id)

    async def notify_manual_intervention(
        self,
        application_id: UUID,
        reason: str,
        chat_id: Optional[int] = None,
    ) -> bool:
        """Alert owner when manual intervention (e.g. CAPTCHA, MFA) is required."""
        msg = (
            f"⚠️ *Manual Intervention Required*\n"
            f"• *App ID*: `{application_id}`\n"
            f"• *Reason*: {reason}\n"
            f"Automation will never bypass security challenges."
        )
        return await self._dispatch_alert(msg, chat_id)

    async def notify_session_expiry(
        self,
        provider: str,
        chat_id: Optional[int] = None,
    ) -> bool:
        """Alert owner when a provider session has expired."""
        msg = (
            f"🔑 *Session Expired*\n"
            f"• *Provider*: {provider}\n"
            f"Please log in manually via browser session runner."
        )
        return await self._dispatch_alert(msg, chat_id)

    async def notify_provider_auto_pause(
        self,
        provider: str,
        reason: str,
        consecutive_failures: int = 3,
        chat_id: Optional[int] = None,
    ) -> bool:
        """Alert owner when a provider has been automatically paused due to consecutive failures."""
        msg = (
            f"🛑 *Provider Auto-Paused*\n"
            f"• *Provider*: {provider}\n"
            f"• *Failures*: {consecutive_failures} consecutive\n"
            f"• *Reason*: {reason}\n"
            f"Use `/resume {provider}` after resolving issues."
        )
        return await self._dispatch_alert(msg, chat_id)

    async def notify_kill_switch_activated(
        self,
        reason: str,
        actor: str = "system",
        chat_id: Optional[int] = None,
    ) -> bool:
        """Alert owner of global emergency kill-switch activation."""
        msg = (
            f"🚨 *KILL SWITCH ACTIVATED*\n"
            f"• *Actor*: {actor}\n"
            f"• *Reason*: {reason}\n"
            f"All worker execution is halted fail-closed."
        )
        return await self._dispatch_alert(msg, chat_id)

    async def notify_llm_budget_exhausted(
        self,
        current_spend_usd: float,
        budget_usd: float,
        chat_id: Optional[int] = None,
    ) -> bool:
        """Alert owner of daily LLM budget exhaustion."""
        msg = (
            f"💸 *LLM Daily Budget Exhausted*\n"
            f"• *Spend*: ${current_spend_usd:.2f} / ${budget_usd:.2f}\n"
            f"Borderline LLM reviews degraded to deterministic matching."
        )
        return await self._dispatch_alert(msg, chat_id)

    async def notify_heartbeat_failure(
        self,
        worker_id: str,
        last_heartbeat: datetime,
        chat_id: Optional[int] = None,
    ) -> bool:
        """Alert owner that worker heartbeat has lapsed during active hours."""
        msg = (
            f"💀 *Worker Dead-Man Alert*\n"
            f"• *Worker ID*: {worker_id}\n"
            f"• *Last Heartbeat*: {last_heartbeat.isoformat()}\n"
            f"Worker inactive for > 2h during IST active hours."
        )
        return await self._dispatch_alert(msg, chat_id)

    async def notify_daily_summary(
        self,
        summary: Dict[str, Any],
        chat_id: Optional[int] = None,
    ) -> bool:
        """Send daily operational summary to owner."""
        msg = (
            f"📊 *Daily Agent Summary*\n"
            f"• Discovered: {summary.get('discovered', 0)}\n"
            f"• Matched: {summary.get('matched', 0)}\n"
            f"• Awaiting Approval: {summary.get('awaiting_approval', 0)}\n"
            f"• Dry-Runs Done: {summary.get('dry_runs_done', 0)}\n"
            f"• Blocked / Rejected: {summary.get('rejected', 0)}\n"
            f"• LLM Spend: ${summary.get('llm_cost_usd', 0.0):.2f}"
        )
        return await self._dispatch_alert(msg, chat_id)

    async def _dispatch_alert(self, text: str, target_chat_id: Optional[int] = None) -> bool:
        """Safely dispatch notification with error containment (never crashes calling flow)."""
        try:
            if target_chat_id:
                if target_chat_id not in self.allowed_chat_ids and self.allowed_chat_ids:
                    logger.warning("Rejecting outbound alert to unauthorized chat_id=%s", target_chat_id)
                    return False
                return await self.notifier.send_message(text, target_chat_id)

            if not self.allowed_chat_ids:
                # Dispatch to default mock
                return await self.notifier.send_message(text, None)

            # Broadcast to all allowed owner chat IDs
            success = True
            for cid in self.allowed_chat_ids:
                sent = await self.notifier.send_message(text, cid)
                if not sent:
                    success = False
            return success
        except Exception as err:
            logger.error("Telegram notification failed (fail-safe): %s", err)
            return False

    # -------------------------------------------------------------------------
    # Inbound Command Processing (Strict allowlist & authorization)
    # -------------------------------------------------------------------------

    async def handle_command(
        self,
        chat_id: int,
        command_text: str,
        user_id: UUID,
    ) -> str:
        """Parse and execute owner commands.

        Commands:
        - /status
        - /kill [reason]
        - /pause [provider]
        - /resume [provider]
        - /approve <app_id>
        - /reject <app_id> [reason]
        """
        # Strict sender verification
        if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            logger.warning("Security alert: Unauthorized Telegram command from chat_id=%s: %s", chat_id, command_text)
            raise TelegramSecurityError(f"Unauthorized chat ID: {chat_id}")

        text = command_text.strip()
        parts = text.split(maxsplit=2)
        if not parts:
            return "Empty command."

        cmd = parts[0].lower()

        if cmd == "/status":
            return await self._cmd_status()

        if cmd == "/kill":
            reason = parts[1] if len(parts) > 1 else "Activated via Telegram /kill command"
            return await self._cmd_kill(reason)

        if cmd == "/pause":
            provider = parts[1] if len(parts) > 1 else "all"
            return await self._cmd_pause(provider)

        if cmd == "/resume":
            provider = parts[1] if len(parts) > 1 else "all"
            return await self._cmd_resume(provider)

        if cmd == "/approve":
            if len(parts) < 2:
                return "Usage: /approve <application_id>"
            try:
                app_id = UUID(parts[1])
            except ValueError:
                return f"Invalid UUID format: {parts[1]}"
            return await self._cmd_approve(app_id, user_id)

        if cmd == "/reject":
            if len(parts) < 2:
                return "Usage: /reject <application_id> [reason]"
            try:
                app_id = UUID(parts[1])
            except ValueError:
                return f"Invalid UUID format: {parts[1]}"
            reason = parts[2] if len(parts) > 2 else "Rejected via Telegram command"
            return await self._cmd_reject(app_id, user_id, reason)

        return f"Unknown command: {cmd}. Supported: /status, /kill, /pause, /resume, /approve, /reject"

    async def _cmd_status(self) -> str:
        status_lines = ["🤖 *Job Agent Status:*"]
        if self.kill_switch:
            is_active = not self.kill_switch.is_automation_enabled()
            status_lines.append(f"• Kill Switch: {'🚨 ACTIVE' if is_active else '✅ Normal'}")

        if self.provider_health_mgr:
            for p, state in self.provider_health_mgr.get_all_states().items():
                status_lines.append(f"• Provider `{p}`: {state.status.value} (consecutive fails: {state.consecutive_failures})")

        return "\n".join(status_lines)

    async def _cmd_kill(self, reason: str) -> str:
        if not self.kill_switch:
            return "Kill switch component unconfigured."
        self.kill_switch.trip(reason=reason, updated_by="telegram_owner")
        await self.notify_kill_switch_activated(reason=reason, actor="telegram_owner")
        return f"🚨 Kill switch ACTIVATED. Reason: {reason}"

    async def _cmd_pause(self, provider: str) -> str:
        if not self.provider_health_mgr:
            return "Provider health manager unconfigured."
        self.provider_health_mgr.pause_provider(provider, reason="Paused via Telegram owner command")
        return f"⏸️ Provider `{provider}` has been PAUSED."

    async def _cmd_resume(self, provider: str) -> str:
        if not self.provider_health_mgr:
            return "Provider health manager unconfigured."
        self.provider_health_mgr.resume_provider(provider)
        return f"▶️ Provider `{provider}` has been RESUMED."

    async def _cmd_approve(self, app_id: UUID, user_id: UUID) -> str:
        if not self.approval_manager:
            return "Approval manager unconfigured."
        try:
            approved = await self.approval_manager.approve_application(
                application_id=app_id,
                user_id=user_id,
                actor="telegram_bot",
            )
            return f"✅ Application `{app_id}` APPROVED. Transitioned to `{approved.status.value}`."
        except Exception as err:
            return f"❌ Approval failed: {err}"

    async def _cmd_reject(self, app_id: UUID, user_id: UUID, reason: str) -> str:
        if not self.approval_manager:
            return "Approval manager unconfigured."
        try:
            rejected = await self.approval_manager.reject_application(
                application_id=app_id,
                user_id=user_id,
                reason=reason,
                actor="telegram_bot",
            )
            return f"🛑 Application `{app_id}` REJECTED. Status: `{rejected.status.value}`."
        except Exception as err:
            return f"❌ Rejection failed: {err}"
