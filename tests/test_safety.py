"""Comprehensive unit tests for the Safety Engine: Kill Switch and Application Caps."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from services.api.config import CapsConfig
from worker.core.caps import (
    ApplicationRecord,
    CapsEnforcer,
    FileApplicationLedger,
    InMemoryApplicationLedger,
)
from worker.core.exceptions import (
    CompanyCooldownExceededError,
    CompanyDailyCapExceededError,
    GlobalDailyCapExceededError,
    InvalidSafetyStateError,
    KillSwitchActiveError,
    ProviderDailyCapExceededError,
    RealSubmitGateBlockedError,
)
from worker.core.kill_switch import FileKillSwitch, InMemoryKillSwitch
from worker.core.safety import SafetyEngine


# ---------------------------------------------------------------------------
# KILL SWITCH TESTS
# ---------------------------------------------------------------------------

def test_in_memory_kill_switch_lifecycle():
    """Verify in-memory kill switch trip, verify, and reset behavior."""
    ks = InMemoryKillSwitch(initial_enabled=True)
    assert ks.is_automation_enabled() is True
    ks.verify_automation_allowed()

    ks.trip(reason="Manual emergency stop")
    assert ks.is_automation_enabled() is False
    with pytest.raises(KillSwitchActiveError) as exc_info:
        ks.verify_automation_allowed()
    assert "manual emergency stop" in str(exc_info.value).lower()

    ks.reset()
    assert ks.is_automation_enabled() is True
    ks.verify_automation_allowed()


def test_file_kill_switch_fails_closed_when_file_missing(tmp_path: Path):
    """Verify FileKillSwitch strictly fails closed if the state file does not exist."""
    missing_path = tmp_path / "non_existent_kill_switch.json"
    ks = FileKillSwitch(missing_path)

    assert ks.is_automation_enabled() is False
    with pytest.raises(InvalidSafetyStateError) as exc_info:
        ks.verify_automation_allowed()
    assert "missing" in str(exc_info.value).lower()


def test_file_kill_switch_fails_closed_when_file_corrupt(tmp_path: Path):
    """Verify FileKillSwitch strictly fails closed if the state file is corrupted."""
    corrupt_path = tmp_path / "corrupt_kill_switch.json"
    corrupt_path.write_text("{invalid_json: 123", encoding="utf-8")
    ks = FileKillSwitch(corrupt_path)

    assert ks.is_automation_enabled() is False
    with pytest.raises(InvalidSafetyStateError) as exc_info:
        ks.verify_automation_allowed()
    assert "corrupted" in str(exc_info.value).lower()


def test_file_kill_switch_persistence_across_restarts(tmp_path: Path):
    """Verify kill switch state persists across simulated process restarts."""
    state_file = tmp_path / "kill_switch.json"
    ks1 = FileKillSwitch(state_file)
    ks1.reset()  # Enable automation and write valid file

    # Re-instantiate as new process would
    ks2 = FileKillSwitch(state_file)
    assert ks2.is_automation_enabled() is True
    ks2.verify_automation_allowed()

    # Trip the switch in process 2
    ks2.trip(reason="UI Canary failure")

    # Process 3 re-reads disk and verifies tripped state is preserved
    ks3 = FileKillSwitch(state_file)
    assert ks3.is_automation_enabled() is False
    with pytest.raises(KillSwitchActiveError):
        ks3.verify_automation_allowed()


# ---------------------------------------------------------------------------
# APPLICATION CAPS TESTS
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_caps_config() -> CapsConfig:
    return CapsConfig(
        global_per_day=3,
        per_provider_per_day={"greenhouse": 2, "lever": 2},
        per_company_per_30d=1,
        per_company_per_day=2,
    )


def test_caps_enforcer_global_daily_limit(sample_caps_config: CapsConfig):
    """Verify global daily application limit boundary conditions."""
    ledger = InMemoryApplicationLedger()
    fixed_time = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)
    enforcer = CapsEnforcer(sample_caps_config, ledger, clock=lambda: fixed_time)

    # 0/3 -> allowed
    enforcer.check_caps(company="Acme Corp", provider="greenhouse", now=fixed_time)

    # Add 2 submissions (different companies and providers)
    ledger.record_submission(
        ApplicationRecord(id="app-1", company="Alpha", provider="lever", applied_at=fixed_time)
    )
    ledger.record_submission(
        ApplicationRecord(id="app-2", company="Beta", provider="lever", applied_at=fixed_time)
    )

    # 2/3 -> allowed
    enforcer.check_caps(company="Acme Corp", provider="greenhouse", now=fixed_time)

    # Add 3rd submission (reaches cap of 3)
    ledger.record_submission(
        ApplicationRecord(id="app-3", company="Gamma", provider="lever", applied_at=fixed_time)
    )

    # 3/3 -> blocked
    with pytest.raises(GlobalDailyCapExceededError) as exc_info:
        enforcer.check_caps(company="Acme Corp", provider="greenhouse", now=fixed_time)
    assert "global daily cap reached: 3/3" in str(exc_info.value).lower()


def test_caps_enforcer_provider_daily_limit(sample_caps_config: CapsConfig):
    """Verify provider-specific daily ceiling boundary conditions."""
    ledger = InMemoryApplicationLedger()
    fixed_time = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)
    enforcer = CapsEnforcer(sample_caps_config, ledger, clock=lambda: fixed_time)

    # Greenhouse limit is 2; global limit is 3
    ledger.record_submission(
        ApplicationRecord(id="app-1", company="Alpha", provider="greenhouse", applied_at=fixed_time)
    )
    ledger.record_submission(
        ApplicationRecord(id="app-2", company="Beta", provider="greenhouse", applied_at=fixed_time)
    )

    # 2/2 greenhouse used -> greenhouse blocked
    with pytest.raises(ProviderDailyCapExceededError) as exc_info:
        enforcer.check_caps(company="Gamma", provider="greenhouse", now=fixed_time)
    assert "provider daily cap reached for 'greenhouse': 2/2" in str(exc_info.value).lower()

    # Lever still has 0/2 used and global has 2/3 used -> lever allowed
    enforcer.check_caps(company="Gamma", provider="lever", now=fixed_time)


def test_caps_enforcer_company_cooldown_30_days(sample_caps_config: CapsConfig):
    """Verify per-company 30-day cooldown enforcement and expiry."""
    ledger = InMemoryApplicationLedger()
    t0 = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    enforcer = CapsEnforcer(sample_caps_config, ledger, clock=lambda: t0)

    # Apply to Stripe at t0
    ledger.record_submission(
        ApplicationRecord(id="app-1", company="Stripe", provider="greenhouse", applied_at=t0)
    )

    # Check 15 days later (within 30-day window) -> blocked
    t_15d = t0 + timedelta(days=15)
    with pytest.raises(CompanyCooldownExceededError) as exc_info:
        enforcer.check_caps(company="Stripe", provider="greenhouse", now=t_15d)
    assert "cooldown in effect for 'stripe': 1/1" in str(exc_info.value).lower()

    # Case-insensitive company check ("stripe" vs "Stripe")
    with pytest.raises(CompanyCooldownExceededError):
        enforcer.check_caps(company="stripe", provider="greenhouse", now=t_15d)

    # Check 31 days later (after 30-day window) -> allowed
    t_31d = t0 + timedelta(days=31)
    enforcer.check_caps(company="Stripe", provider="greenhouse", now=t_31d)


def test_caps_enforcer_company_daily_limit():
    """Verify per-company 24-hour limit enforcement."""
    caps_cfg = CapsConfig(
        global_per_day=10,
        per_provider_per_day={"greenhouse": 10},
        per_company_per_30d=5,  # Allow multiple per month to test daily limit
        per_company_per_day=2,
    )
    ledger = InMemoryApplicationLedger()
    t0 = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)
    enforcer = CapsEnforcer(caps_cfg, ledger, clock=lambda: t0)

    # 2 applications to Google within 2 hours
    ledger.record_submission(
        ApplicationRecord(id="app-1", company="Google", provider="greenhouse", applied_at=t0 - timedelta(hours=2))
    )
    ledger.record_submission(
        ApplicationRecord(id="app-2", company="Google", provider="greenhouse", applied_at=t0 - timedelta(hours=1))
    )

    # 3rd application within 24 hours -> blocked by daily company limit
    with pytest.raises(CompanyDailyCapExceededError) as exc_info:
        enforcer.check_caps(company="Google", provider="greenhouse", now=t0)
    assert "company daily limit reached for 'google': 2/2" in str(exc_info.value).lower()


def test_file_application_ledger_persistence(tmp_path: Path):
    """Verify FileApplicationLedger retains accounting across process restarts."""
    ledger_file = tmp_path / "ledger.jsonl"
    t0 = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)

    # Process 1 writes records
    l1 = FileApplicationLedger(ledger_file)
    l1.record_submission(
        ApplicationRecord(id="app-1", company="Meta", provider="greenhouse", applied_at=t0)
    )

    # Process 2 reads records
    l2 = FileApplicationLedger(ledger_file)
    assert l2.count_daily_applications(t0.date()) == 1
    assert l2.count_company_applications_since("Meta", since=t0 - timedelta(hours=1)) == 1


def test_file_application_ledger_corrupted_fails_closed(tmp_path: Path):
    """Verify corrupted ledger entries raise InvalidSafetyStateError."""
    ledger_file = tmp_path / "corrupt_ledger.jsonl"
    ledger_file.write_text("invalid json entry\n", encoding="utf-8")

    ledger = FileApplicationLedger(ledger_file)
    with pytest.raises(InvalidSafetyStateError) as exc_info:
        ledger.count_daily_applications(datetime.now(timezone.utc).date())
    assert "corrupted ledger entry" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# SAFETY ENGINE EXECUTION BARRIER TESTS
# ---------------------------------------------------------------------------

def test_safety_engine_evaluates_and_blocks_tripped_kill_switch(sample_caps_config: CapsConfig):
    """Verify SafetyEngine blocks when kill switch is engaged."""
    ks = InMemoryKillSwitch(initial_enabled=False)
    ledger = InMemoryApplicationLedger()
    enforcer = CapsEnforcer(sample_caps_config, ledger)
    engine = SafetyEngine(kill_switch=ks, caps_enforcer=enforcer)

    decision = engine.evaluate_pre_apply(company="Acme", provider="greenhouse")
    assert decision.allowed is False
    assert decision.blocked_by == "kill_switch"

    with pytest.raises(KillSwitchActiveError):
        engine.verify_pre_apply(company="Acme", provider="greenhouse")


def test_safety_engine_blocks_real_submit_without_gate():
    """Verify SafetyEngine strictly blocks real submissions when gate is locked."""
    ks = InMemoryKillSwitch(initial_enabled=True)
    ledger = InMemoryApplicationLedger()
    caps_cfg = CapsConfig(global_per_day=10)
    enforcer = CapsEnforcer(caps_cfg, ledger)
    engine = SafetyEngine(kill_switch=ks, caps_enforcer=enforcer, real_submit_gate_enabled=False)

    decision = engine.evaluate_pre_apply(company="Acme", provider="greenhouse", is_real_submit=True)
    assert decision.allowed is False
    assert decision.blocked_by == "real_submit_gate"
    assert "real-submit gate" in decision.reason.lower()

    with pytest.raises(RealSubmitGateBlockedError):
        engine.verify_pre_apply(company="Acme", provider="greenhouse", is_real_submit=True)


def test_safety_engine_permits_valid_dry_run_within_caps(sample_caps_config: CapsConfig):
    """Verify SafetyEngine permits valid dry-run applications within limits."""
    ks = InMemoryKillSwitch(initial_enabled=True)
    ledger = InMemoryApplicationLedger()
    enforcer = CapsEnforcer(sample_caps_config, ledger)
    engine = SafetyEngine(kill_switch=ks, caps_enforcer=enforcer)

    decision = engine.evaluate_pre_apply(company="Acme", provider="greenhouse", is_real_submit=False)
    assert decision.allowed is True
    assert decision.blocked_by is None

    # Does not raise
    engine.verify_pre_apply(company="Acme", provider="greenhouse", is_real_submit=False)
