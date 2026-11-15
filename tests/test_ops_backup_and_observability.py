"""Unit tests for Phase 2.6: Telegram reliability, structured observability, and backup recovery.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import pytest
from uuid import uuid4

from services.api.logging_config import (
    JSONFormatter,
    bind_logging_context,
    format_audit_log,
)
from worker.ops.backup import (
    BackupIntegrityError,
    BackupManager,
    compute_payload_checksum,
)
from worker.ops.telegram import (
    AlertDeduplicator,
    DeliveryStatus,
    MockTelegramNotifier,
    NotificationDeliveryRecord,
    NotificationOutbox,
    TelegramNotificationService,
    TelegramNotifier,
)


# -----------------------------------------------------------------------------
# 1. Telegram Notifications & Outbox Tests
# -----------------------------------------------------------------------------

def test_alert_deduplicator_cooldown():
    """Verify duplicate alert suppression within cooldown window and allow after expiry."""
    dedup = AlertDeduplicator(cooldown_seconds=300)
    now = datetime.now(timezone.utc)
    text = "⚠️ Provider naukri auto-paused due to consecutive errors"

    # First dispatch -> Not duplicate
    assert dedup.is_duplicate(text, chat_id=12345, as_of=now) is False

    # Immediate second dispatch -> Duplicate suppressed
    assert dedup.is_duplicate(text, chat_id=12345, as_of=now + timedelta(seconds=10)) is True

    # Different chat ID -> Not duplicate
    assert dedup.is_duplicate(text, chat_id=67890, as_of=now + timedelta(seconds=20)) is False

    # After cooldown expires (301 seconds) -> Not duplicate
    assert dedup.is_duplicate(text, chat_id=12345, as_of=now + timedelta(seconds=301)) is False


class FlakyNotifier(TelegramNotifier):
    """Notifier that fails N times before succeeding."""

    def __init__(self, failures_before_success: int = 2) -> None:
        self.failures_before_success = failures_before_success
        self.attempts = 0

    async def send_message(self, text: str, chat_id: int | None = None) -> bool:
        self.attempts += 1
        if self.attempts <= self.failures_before_success:
            raise ConnectionError(f"Network glitch attempt {self.attempts}")
        return True


@pytest.mark.asyncio
async def test_telegram_retry_mechanism():
    """Verify bounded retry with exponential backoff successfully sends after transient failure."""
    flaky = FlakyNotifier(failures_before_success=2)
    service = TelegramNotificationService(
        bot_token="test-token",
        allowed_chat_ids=[111],
        notifier=flaky,
        max_retries=3,
        retry_backoff_base=0.01,
    )

    result = await service._dispatch_alert("Test transient failure retry", target_chat_id=111)
    assert result is True
    assert flaky.attempts == 3

    outbox_records = service.outbox.get_all()
    assert len(outbox_records) == 1
    assert outbox_records[0].status == DeliveryStatus.SENT


@pytest.mark.asyncio
async def test_telegram_outbox_queue_and_flush():
    """Verify failed alerts are queued in outbox and flushed upon recovery."""
    class FailingNotifier(TelegramNotifier):
        async def send_message(self, text: str, chat_id: int | None = None) -> bool:
            raise ConnectionError("Server unreachable")

    failing = FailingNotifier()
    service = TelegramNotificationService(
        bot_token="test-token",
        allowed_chat_ids=[222],
        notifier=failing,
        max_retries=2,
        retry_backoff_base=0.01,
    )

    result = await service._dispatch_alert("Urgent alert failed", target_chat_id=222)
    assert result is False

    pending = service.outbox.get_pending()
    assert len(pending) == 1
    assert pending[0].status == DeliveryStatus.FAILED
    assert pending[0].target_chat_id == 222

    # Recover with working notifier and flush
    recovery_notifier = MockTelegramNotifier()
    flushed = await service.outbox.flush(recovery_notifier, max_retries=3, backoff_base=0.01)
    assert flushed == 1
    assert len(service.outbox.get_pending()) == 0


# -----------------------------------------------------------------------------
# 2. Centralized Observability & Logging Tests
# -----------------------------------------------------------------------------

def test_bind_logging_context_and_json_formatter():
    """Verify trace variables are bound in context and serialized into JSON log records."""
    formatter = JSONFormatter(service_name="test-worker")
    log_record = logging.LogRecord(
        name="worker.core",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Execution cycle started",
        args=(),
        exc_info=None,
    )

    # Without context
    raw_json = formatter.format(log_record)
    data = json.loads(raw_json)
    assert data["message"] == "Execution cycle started"
    assert data["run_id"] is None
    assert data["provider"] is None

    # With bound context
    with bind_logging_context(run_id="run-99", application_id="app-123", provider="greenhouse", request_id="req-abc"):
        raw_context_json = formatter.format(log_record)
        data_ctx = json.loads(raw_context_json)
        assert data_ctx["run_id"] == "run-99"
        assert data_ctx["application_id"] == "app-123"
        assert data_ctx["provider"] == "greenhouse"
        assert data_ctx["request_id"] == "req-abc"

    # Context resets after scope exits
    raw_after = formatter.format(log_record)
    assert json.loads(raw_after)["run_id"] is None


def test_format_audit_log_with_redaction():
    """Verify audit log event formatting scrubs sensitive fields."""
    with bind_logging_context(run_id="run-1", application_id="app-42"):
        audit = format_audit_log(
            event_type="FORM_INSPECTED",
            actor="operator_1",
            action="INSPECT_FIELDS",
            target_type="application",
            target_id="app-42",
            details={
                "fields_count": 8,
                "api_key": "secret-key-12345",
                "candidate_password": "super-secret-pwd",
            },
        )

        assert audit["event_type"] == "FORM_INSPECTED"
        assert audit["actor"] == "operator_1"
        assert audit["run_id"] == "run-1"
        assert audit["application_id"] == "app-42"
        # Verify secret fields are redacted
        assert audit["details"]["api_key"] == "[REDACTED]"
        assert audit["details"]["candidate_password"] == "[REDACTED]"
        assert audit["details"]["fields_count"] == 8


# -----------------------------------------------------------------------------
# 3. Backup, Verification & Recovery Tests
# -----------------------------------------------------------------------------

def test_backup_creation_and_integrity_verification(tmp_path):
    """Verify backup archive generation with valid SHA-256 checksum and tampering detection."""
    answer_entries = [
        {"key": "notice_period", "value": "30 days", "category": "general"},
        {"key": "relocation", "value": False, "category": "work_preferences"},
    ]
    apps = [
        {"id": str(uuid4()), "company": "Acme Corp", "status": "APPLIED"},
    ]

    bundle = BackupManager.create_backup(
        answer_bank_entries=answer_entries,
        applications=apps,
        output_path=tmp_path / "backup.json",
    )

    assert bundle.metadata.item_counts["answer_bank"] == 2
    assert bundle.metadata.item_counts["applications"] == 1
    assert bundle.metadata.checksum_sha256 is not None

    # Verify integrity of untampered backup
    assert BackupManager.verify_backup_integrity(bundle) is True
    assert BackupManager.verify_backup_integrity(tmp_path / "backup.json") is True

    # Tamper with backup payload -> Checksum verification fails
    bundle.data["answer_bank"][0]["value"] = "90 days (tampered)"
    assert BackupManager.verify_backup_integrity(bundle) is False


def test_backup_restore_and_tamper_rejection():
    """Verify restore succeeds on valid backups and fails closed with BackupIntegrityError on corruption."""
    answer_entries = [{"key": "visa_status", "value": "Citizen", "category": "legal"}]
    bundle = BackupManager.create_backup(answer_bank_entries=answer_entries)

    # Valid restore
    result = BackupManager.restore_backup(bundle)
    assert result.verified is True
    assert result.restored_counts["answer_bank"] == 1

    # Tampered backup restore fails closed
    bundle.data["answer_bank"].append({"key": "illegal_key", "value": "injected"})
    with pytest.raises(BackupIntegrityError):
        BackupManager.restore_backup(bundle)
