"""Telegram Notification and Owner Command Adapter (Phase 1.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Appendix B)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
import hashlib
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

from worker.application.models import Application, ApplicationStatus
from worker.ops.approval import ApprovalManager

logger = logging.getLogger(__name__)


class TelegramSecurityError(Exception):
    """Raised when an unauthorized Telegram user or chat attempts an operation."""


class DeliveryStatus(str, Enum):
    """Status of notification delivery."""

    SENT = "SENT"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"
    QUEUED = "QUEUED"


class NotificationDeliveryRecord(BaseModel):
    """Record tracking notification dispatch attempts, status, and metadata."""

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(default_factory=lambda: uuid4().hex)
    text: str
    target_chat_id: Optional[int] = None
    status: DeliveryStatus = DeliveryStatus.QUEUED
    attempts: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    delivered_at: Optional[datetime] = None


class AlertDeduplicator:
    """Suppresses duplicate or repeating alert bursts within a configurable time window."""

    def __init__(self, cooldown_seconds: int = 600) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._recent_alerts: Dict[str, datetime] = {}

    def _hash_alert(self, text: str, chat_id: Optional[int]) -> str:
        # Normalize whitespace and compute stable content hash
        norm_text = re.sub(r"\s+", " ", text.strip())
        key = f"{chat_id}:{norm_text}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def is_duplicate(self, text: str, chat_id: Optional[int], as_of: Optional[datetime] = None) -> bool:
        """Return True if an identical alert was recorded within the cooldown window."""
        now = as_of or datetime.now(timezone.utc)
        alert_hash = self._hash_alert(text, chat_id)
        last_sent = self._recent_alerts.get(alert_hash)

        if last_sent is not None:
            elapsed = (now - last_sent).total_seconds()
            if elapsed < self.cooldown_seconds:
                return True

        self._recent_alerts[alert_hash] = now
        # Prune entries older than 2x cooldown to prevent memory bloat
        cutoff = now.timestamp() - (self.cooldown_seconds * 2)
        self._recent_alerts = {k: v for k, v in self._recent_alerts.items() if v.timestamp() > cutoff}
        return False


class NotificationOutbox:
    """Maintains a failure/outbox queue of undelivered notifications for recovery."""

    def __init__(self) -> None:
        self._records: Dict[str, NotificationDeliveryRecord] = {}

    def enqueue(self, record: NotificationDeliveryRecord) -> None:
        self._records[record.record_id] = record

    def get_record(self, record_id: str) -> Optional[NotificationDeliveryRecord]:
        return self._records.get(record_id)

    def get_pending(self) -> List[NotificationDeliveryRecord]:
        return [r for r in self._records.values() if r.status in (DeliveryStatus.QUEUED, DeliveryStatus.FAILED)]

    def get_all(self) -> List[NotificationDeliveryRecord]:
        return list(self._records.values())

    async def flush(
        self,
        notifier: TelegramNotifier,
        max_retries: int = 3,
        backoff_base: float = 0.05,
    ) -> int:
        """Retry sending queued notifications up to max_retries with exponential backoff."""
        pending = self.get_pending()
        flushed_count = 0

        for r in pending:
            if r.attempts >= max_retries:
                r.status = DeliveryStatus.FAILED
                continue

            r.attempts += 1
            try:
                success = await notifier.send_message(r.text, r.target_chat_id)
                if success:
                    r.status = DeliveryStatus.SENT
                    r.delivered_at = datetime.now(timezone.utc)
                    flushed_count += 1
                else:
                    r.status = DeliveryStatus.FAILED
                    r.last_error = "Notifier returned False"
            except Exception as ex:
                r.last_error = str(ex)
                r.status = DeliveryStatus.FAILED

            if r.status != DeliveryStatus.SENT and backoff_base > 0:
                await asyncio.sleep(backoff_base * (2 ** (r.attempts - 1)))

        return flushed_count


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
        deduplicator: Optional[AlertDeduplicator] = None,
        outbox: Optional[NotificationOutbox] = None,
        max_retries: int = 3,
        retry_backoff_base: float = 0.05,
    ) -> None:
        self.bot_token = bot_token
        self.allowed_chat_ids: Set[int] = set(allowed_chat_ids or [])
        self.is_live_configured = bool(bot_token and self.allowed_chat_ids)
        self.notifier = notifier or MockTelegramNotifier()
        self.approval_manager = approval_manager
        self.kill_switch = kill_switch
        self.provider_health_mgr = provider_health_mgr
        self.deduplicator = deduplicator or AlertDeduplicator()
        self.outbox = outbox or NotificationOutbox()
        self.max_retries = max(1, max_retries)
        self.retry_backoff_base = retry_backoff_base

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

    async def _send_with_retries(self, text: str, cid: Optional[int]) -> bool:
        """Send message to a single chat ID with bounded retries and exponential backoff."""
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                sent = await self.notifier.send_message(text, cid)
                if sent:
                    return True
                last_error = "Notifier returned False"
            except Exception as ex:
                last_error = str(ex)
                logger.warning(
                    "Telegram send attempt %d/%d failed for chat_id=%s: %s",
                    attempt,
                    self.max_retries,
                    cid,
                    ex,
                )

            if attempt < self.max_retries and self.retry_backoff_base > 0:
                await asyncio.sleep(self.retry_backoff_base * (2 ** (attempt - 1)))

        raise RuntimeError(f"All {self.max_retries} attempts failed: {last_error}")

    async def _dispatch_alert(self, text: str, target_chat_id: Optional[int] = None) -> bool:
        """Safely dispatch notification with deduplication, retries, and outbox failure containment."""
        try:
            # 1. Duplicate alert suppression
            if self.deduplicator.is_duplicate(text, target_chat_id):
                logger.info("Suppressed duplicate alert (chat_id=%s): %s", target_chat_id, text[:60])
                record = NotificationDeliveryRecord(
                    text=text,
                    target_chat_id=target_chat_id,
                    status=DeliveryStatus.SUPPRESSED,
                    delivered_at=datetime.now(timezone.utc),
                )
                self.outbox.enqueue(record)
                return True

            # 2. Authorization filter
            targets: List[Optional[int]]
            if target_chat_id:
                if target_chat_id not in self.allowed_chat_ids and self.allowed_chat_ids:
                    logger.warning("Rejecting outbound alert to unauthorized chat_id=%s", target_chat_id)
                    return False
                targets = [target_chat_id]
            else:
                targets = list(self.allowed_chat_ids) if self.allowed_chat_ids else [None]

            # 3. Dispatch to all targets with retries
            overall_success = True
            for cid in targets:
                record = NotificationDeliveryRecord(
                    text=text,
                    target_chat_id=cid,
                    max_retries=self.max_retries,
                )
                try:
                    await self._send_with_retries(text, cid)
                    record.status = DeliveryStatus.SENT
                    record.delivered_at = datetime.now(timezone.utc)
                except Exception as err:
                    overall_success = False
                    record.status = DeliveryStatus.FAILED
                    record.last_error = str(err)
                    logger.error("Failed to deliver alert to chat_id=%s after retries: %s", cid, err)
                finally:
                    self.outbox.enqueue(record)

            return overall_success
        except Exception as err:
            logger.error("Telegram notification failed (fail-safe): %s", err)
            return False

    async def flush_outbox(self) -> int:
        """Retry sending any queued or failed notifications in the outbox."""
        return await self.outbox.flush(
            self.notifier,
            max_retries=self.max_retries,
            backoff_base=self.retry_backoff_base,
        )

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
