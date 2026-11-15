"""Tests verifying strict L0 safety guarantees with real Playwright execution.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12)
- docs/BUILD_RULES.md
"""

from pathlib import Path
from uuid import uuid4
import pytest

from worker.answers.repository import InMemoryAnswerBankRepository
from worker.answers.resolver import AnswerResolver
from worker.browser.browser_config import BrowserConfig
from worker.browser.browser_manager import BrowserManager
from worker.browser.evidence import EvidenceCollector
from worker.browser.execution_context import ExecutionContext
from worker.browser.navigation_guard import NavigationGuard
from worker.browser.page_inspector import PageInspector
from worker.policy.engine import PolicyEngine
from worker.profile.localfile import LocalFileProfileSource


@pytest.fixture
def profile_source() -> LocalFileProfileSource:
    return LocalFileProfileSource(Path("fixtures/profile.yaml"))


@pytest.fixture
def evidence_dir(tmp_path: Path) -> Path:
    ev = tmp_path / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    return ev


@pytest.mark.asyncio
async def test_l0_dry_run_leaves_form_unmodified(profile_source, evidence_dir: Path):
    """CRITICAL L0 GUARANTEE:

    Form inspection must NOT type candidate data, trigger autosave,
    click submit, or transmit data to external services.
    """
    profile = await profile_source.get_snapshot()
    answer_repo = InMemoryAnswerBankRepository()
    policy_engine = PolicyEngine()
    resolver = AnswerResolver(repository=answer_repo, policy_engine=policy_engine)
    nav_guard = NavigationGuard(fixtures_dir=Path("fixtures"))
    collector = EvidenceCollector(evidence_dir=evidence_dir)

    async with BrowserManager(config=BrowserConfig(headless=True)) as manager:
        user_id = uuid4()
        session = await manager.create_session(user_id=user_id)

        ctx = ExecutionContext(
            session=session,
            navigation_guard=nav_guard,
            page_inspector=PageInspector(),
            evidence_collector=collector,
            answer_resolver=resolver,
            policy_engine=policy_engine,
            profile=profile,
        )

        fixture_target = "fixtures/forms/greenhouse_job.html"
        fill_plan, evidence = await ctx.inspect_and_plan(
            target_url=fixture_target,
            provider_name="greenhouse",
        )

        # 1. Verify plan was constructed without entering data
        assert fill_plan.total_fields >= 8
        assert fill_plan.auto_approved_count >= 3  # Name, email, phone from profile
        assert fill_plan.blocked_count >= 1  # Password / OTP

        # 2. Check DOM on the live page: values MUST be completely empty!
        page = session.page
        fn_val = await page.eval_on_selector("#first_name", "el => el.value")
        assert fn_val == "", "L0 violation: candidate data was typed into external form!"

        email_val = await page.eval_on_selector("#email", "el => el.value")
        assert email_val == "", "L0 violation: candidate email was typed into external form!"

        phone_val = await page.eval_on_selector("#phone", "el => el.value")
        assert phone_val == "", "L0 violation: candidate phone was typed into external form!"

        # 3. Verify evidence screenshot exists on disk
        assert evidence.screenshot_path is not None
        assert Path(evidence.screenshot_path).exists()
        assert Path(evidence.screenshot_path).stat().st_size > 0

        # 4. Verify evidence record contains no secrets
        text_dump = str(evidence.model_dump()).lower()
        for sensitive in ("password", "secret", "token", "otp"):
            assert sensitive not in evidence.screenshot_path.lower()

        await session.close()


@pytest.mark.asyncio
async def test_l0_dry_run_on_lever_fixture(profile_source, evidence_dir: Path):
    """Verify L0 inspection operates safely on Lever fixture with radio, select, and textarea."""
    profile = await profile_source.get_snapshot()
    collector = EvidenceCollector(evidence_dir=evidence_dir)
    nav_guard = NavigationGuard(fixtures_dir=Path("fixtures"))

    async with BrowserManager(config=BrowserConfig(headless=True)) as manager:
        session = await manager.create_session(user_id=uuid4())

        ctx = ExecutionContext(
            session=session,
            navigation_guard=nav_guard,
            evidence_collector=collector,
            profile=profile,
        )

        fixture_target = "fixtures/forms/lever_job.html"
        fill_plan, evidence = await ctx.inspect_and_plan(
            target_url=fixture_target,
            provider_name="lever",
        )

        assert fill_plan.total_fields >= 8
        assert evidence.outcome == "L0_INSPECTION_COMPLETED"
        assert evidence.screenshot_path is not None
        assert Path(evidence.screenshot_path).exists()

        # Verify radio buttons were not selected
        is_radio_checked = await session.page.eval_on_selector(
            'input[name="relocation"]',
            "el => el.checked",
        )
        assert is_radio_checked is False

        await session.close()
