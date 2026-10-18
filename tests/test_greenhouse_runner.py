"""Unit and fixture-based tests for GreenhouseProvider and JobApplicationRunner."""

from pathlib import Path
import pytest
from playwright.async_api import async_playwright

from services.api.config import CapsConfig
from worker.core.caps import CapsEnforcer, InMemoryApplicationLedger
from worker.core.exceptions import (
    GlobalDailyCapExceededError,
    KillSwitchActiveError,
    RealSubmitGateBlockedError,
)
from worker.core.kill_switch import InMemoryKillSwitch
from worker.core.runner import JobApplicationRunner
from worker.core.safety import SafetyEngine
from worker.profile.localfile import LocalFileProfileSource
from worker.providers.greenhouse import GreenhouseProvider


@pytest.fixture
def test_profile_source() -> LocalFileProfileSource:
    return LocalFileProfileSource("fixtures/profile.yaml")


@pytest.fixture
def safety_engine() -> SafetyEngine:
    ks = InMemoryKillSwitch(initial_enabled=True)
    caps_cfg = CapsConfig(global_per_day=10, per_company_per_day=5, per_company_per_30d=5)
    ledger = InMemoryApplicationLedger()
    enforcer = CapsEnforcer(caps_cfg, ledger)
    return SafetyEngine(kill_switch=ks, caps_enforcer=enforcer, real_submit_gate_enabled=False)


@pytest.mark.asyncio
async def test_runner_blocks_when_kill_switch_active(
    test_profile_source: LocalFileProfileSource,
    safety_engine: SafetyEngine,
):
    """Verify runner halts immediately before any browser interaction if kill switch is active."""
    safety_engine.kill_switch.trip(reason="Emergency kill switch test")

    runner = JobApplicationRunner(
        safety_engine=safety_engine,
        profile_source=test_profile_source,
    )

    with pytest.raises(KillSwitchActiveError):
        await runner.execute_dry_run(
            job_url_or_path="http://dummy-url.local",
            company="Acme Corp",
            provider_name="greenhouse",
        )


@pytest.mark.asyncio
async def test_runner_blocks_when_daily_cap_exceeded(
    test_profile_source: LocalFileProfileSource,
):
    """Verify runner halts before browser action if daily cap is exceeded."""
    ks = InMemoryKillSwitch(initial_enabled=True)
    caps_cfg = CapsConfig(global_per_day=0)  # 0 limit -> immediately blocked
    ledger = InMemoryApplicationLedger()
    enforcer = CapsEnforcer(caps_cfg, ledger)
    engine = SafetyEngine(kill_switch=ks, caps_enforcer=enforcer)

    runner = JobApplicationRunner(safety_engine=engine, profile_source=test_profile_source)

    with pytest.raises(GlobalDailyCapExceededError):
        await runner.execute_dry_run(
            job_url_or_path="http://dummy-url.local",
            company="Acme Corp",
            provider_name="greenhouse",
        )


@pytest.mark.asyncio
async def test_runner_rejects_unregistered_provider(
    test_profile_source: LocalFileProfileSource,
    safety_engine: SafetyEngine,
):
    """Verify runner rejects unsupported provider names with typed error."""
    fixture_path = Path("fixtures/forms/greenhouse_job.html").resolve()
    runner = JobApplicationRunner(
        safety_engine=safety_engine,
        profile_source=test_profile_source,
    )

    with pytest.raises(ValueError) as exc_info:
        await runner.execute_dry_run(
            job_url_or_path=fixture_path.as_uri(),
            company="Acme Corp",
            provider_name="unsupported_provider",
        )
    assert "unsupported job board provider" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_runner_rejects_external_http_and_https_urls(
    test_profile_source: LocalFileProfileSource,
    safety_engine: SafetyEngine,
):
    """Verify runner strictly rejects external HTTP and HTTPS URLs before browser action."""
    runner = JobApplicationRunner(safety_engine=safety_engine, profile_source=test_profile_source)

    for external_url in ("http://boards.greenhouse.io/jobs/123", "https://example.com/apply"):
        with pytest.raises(ValueError) as exc_info:
            await runner.execute_dry_run(
                job_url_or_path=external_url,
                company="Acme Corp",
                provider_name="greenhouse",
            )
        assert "external navigation rejected" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_runner_rejects_unsupported_schemes(
    test_profile_source: LocalFileProfileSource,
    safety_engine: SafetyEngine,
):
    """Verify runner rejects dangerous or unsupported schemes (ftp, javascript, data)."""
    runner = JobApplicationRunner(safety_engine=safety_engine, profile_source=test_profile_source)

    for invalid_target in ("ftp://files.example.com/job.html", "javascript:alert(1)", "data:text/html,<h1>Job</h1>"):
        with pytest.raises(ValueError) as exc_info:
            await runner.execute_dry_run(
                job_url_or_path=invalid_target,
                company="Acme Corp",
                provider_name="greenhouse",
            )
        assert "scheme" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_runner_rejects_path_traversal_and_outside_fixtures(
    test_profile_source: LocalFileProfileSource,
    safety_engine: SafetyEngine,
):
    """Verify runner rejects path traversal and paths outside approved fixtures directory."""
    runner = JobApplicationRunner(safety_engine=safety_engine, profile_source=test_profile_source)

    # 1. Traversal outside fixtures/forms
    with pytest.raises(ValueError) as exc_info:
        await runner.execute_dry_run(
            job_url_or_path="fixtures/forms/../../config/config.yaml",
            company="Acme Corp",
            provider_name="greenhouse",
        )
    assert "path traversal rejected" in str(exc_info.value).lower()

    # 2. Existing file outside fixtures/forms
    with pytest.raises(ValueError) as exc_info2:
        await runner.execute_dry_run(
            job_url_or_path="fixtures/profile.yaml",
            company="Acme Corp",
            provider_name="greenhouse",
        )
    assert "outside approved directory" in str(exc_info2.value).lower()


@pytest.mark.asyncio
async def test_runner_rejects_non_existent_fixture(
    test_profile_source: LocalFileProfileSource,
    safety_engine: SafetyEngine,
):
    """Verify runner rejects non-existent fixture paths before browser action."""
    runner = JobApplicationRunner(safety_engine=safety_engine, profile_source=test_profile_source)

    with pytest.raises(ValueError) as exc_info:
        await runner.execute_dry_run(
            job_url_or_path="fixtures/forms/does_not_exist.html",
            company="Acme Corp",
            provider_name="greenhouse",
        )
    assert "fixture file does not exist" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_greenhouse_dry_run_form_filling_with_local_fixture(
    tmp_path: Path,
    test_profile_source: LocalFileProfileSource,
    safety_engine: SafetyEngine,
):
    """Verify truthful dry-run form filling, sensitive field skipping, and unresolved fields on local fixture."""
    fixture_path = Path("fixtures/forms/greenhouse_job.html").resolve()
    assert fixture_path.exists(), "Greenhouse fixture HTML must exist"

    evidence_dir = tmp_path / "evidence"
    runner = JobApplicationRunner(
        safety_engine=safety_engine,
        profile_source=test_profile_source,
        evidence_dir=evidence_dir,
    )

    file_url = fixture_path.as_uri()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        # Execute dry-run via central runner
        result = await runner.execute_dry_run(
            job_url_or_path=file_url,
            company="Example Software",
            provider_name="greenhouse",
            page=page,
        )

        # 1. Verify standard identity fields were truthfully filled from profile
        assert result.status == "DRY_RUN_COMPLETED"
        assert result.provider == "greenhouse"
        assert result.company == "Example Software"
        assert result.fields_filled.get("First Name *") == "Candidate"
        assert result.fields_filled.get("Last Name *") == "Name Placeholder"
        assert result.fields_filled.get("Email *") == "candidate.placeholder@example.com"
        assert result.fields_filled.get("Phone *") == "+1-555-0100"
        assert result.fields_filled.get("LinkedIn Profile") == "https://linkedin.com/in/example-candidate"

        # 2. Verify unknown / policy fields remain unresolved and NOT fabricated
        unresolved_str = " ".join(result.unresolved_fields).lower()
        assert "notice period" in unresolved_str
        assert "why are you interested" in unresolved_str

        # 3. Verify in the DOM that resolved fields have values and custom fields remain empty
        first_name_val = await page.input_value("#first_name")
        assert first_name_val == "Candidate"

        email_val = await page.input_value("#email")
        assert email_val == "candidate.placeholder@example.com"

        notice_period_val = await page.input_value("#job_application_answers_attributes_2_text_value")
        assert notice_period_val == "", "Unresolved notice period question must NOT be filled"

        why_join_val = await page.input_value("#job_application_answers_attributes_3_text_value")
        assert why_join_val == "", "Unresolved free-text question must NOT be filled"

        # 4. Verify sensitive fields (file, password, OTP) remain completely untouched and unpopulated
        assert await page.input_value("#account_password") == "", "Password field must never be populated"
        assert await page.input_value("#otp_verification") == "", "OTP field must never be populated"
        assert "Resume / CV" not in result.fields_filled
        assert "Create Password" not in result.fields_filled
        assert "Enter One-Time Password (OTP)" not in result.fields_filled

        # 5. Verify screenshot was captured in evidence directory
        assert result.screenshot_path is not None
        assert Path(result.screenshot_path).exists()
        assert Path(result.screenshot_path).stat().st_size > 0

        # 6. Verify page did NOT submit (form action was not triggered, stays on page)
        assert await page.is_visible("#submit_app")

        await browser.close()


@pytest.mark.asyncio
async def test_runner_self_managed_browser_with_valid_fixture(
    tmp_path: Path,
    test_profile_source: LocalFileProfileSource,
    safety_engine: SafetyEngine,
):
    """Verify runner self-managed Playwright session successfully navigates and executes dry-run."""
    fixture_path = Path("fixtures/forms/greenhouse_job.html").resolve()
    evidence_dir = tmp_path / "evidence_self_managed"

    runner = JobApplicationRunner(
        safety_engine=safety_engine,
        profile_source=test_profile_source,
        evidence_dir=evidence_dir,
    )

    result = await runner.execute_dry_run(
        job_url_or_path=str(fixture_path),
        company="Example Software",
        provider_name="greenhouse",
        page=None,  # Self-managed Playwright session
    )

    assert result.status == "DRY_RUN_COMPLETED"
    assert result.fields_filled.get("First Name *") == "Candidate"
    assert result.screenshot_path is not None
    assert Path(result.screenshot_path).exists()


@pytest.mark.asyncio
async def test_greenhouse_provider_strictly_rejects_real_submission(
    test_profile_source: LocalFileProfileSource,
):
    """Verify GreenhouseProvider raises RealSubmitGateBlockedError if dry_run=False."""
    provider = GreenhouseProvider()
    profile = await test_profile_source.get_snapshot()

    with pytest.raises(RealSubmitGateBlockedError) as exc_info:
        await provider.inspect_and_fill(page=None, profile=profile, dry_run=False)

    assert "real-submit gate is locked" in str(exc_info.value).lower()
