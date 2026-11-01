"""Tests for Form Parsing Foundation and integration with AnswerResolver and PolicyEngine."""

from pathlib import Path
import pytest

from worker.answers.models import AnswerBankEntry, AnswerSource, AnswerType, ResolutionStatus
from worker.answers.repository import InMemoryAnswerBankRepository
from worker.answers.resolver import AnswerResolver
from worker.policy.engine import PolicyEngine
from worker.policy.taxonomy import FieldCategory, PolicyType
from worker.profile.localfile import LocalFileProfileSource
from worker.profile.models import ProfileSnapshot
from worker.providers.base import FormField, FormFillResult
from worker.providers.greenhouse import GreenhouseProvider, parse_greenhouse_form_html


@pytest.fixture
def form_html() -> str:
    path = Path("fixtures/forms/greenhouse_job.html")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def profile() -> ProfileSnapshot:
    source = LocalFileProfileSource(Path("fixtures/profile.yaml"))
    return source.load_snapshot()


@pytest.fixture
def answer_repo() -> InMemoryAnswerBankRepository:
    repo = InMemoryAnswerBankRepository()
    return repo


class TestFormParsingFoundation:
    def test_extract_form_fields_metadata(self, form_html: str, profile: ProfileSnapshot):
        """Verify extraction of normalized form field metadata from Greenhouse HTML fixture."""
        fields = parse_greenhouse_form_html(form_html, profile=profile)

        # Total fields in fixtures/forms/greenhouse_job.html:
        # first_name, last_name, email, phone, linkedin, website, notice_period, why_join (textarea),
        # resume (file), password, otp
        assert len(fields) >= 10

        field_map = {f.field_id: f for f in fields}

        # First Name
        fn = field_map["first_name"]
        assert fn.label == "First Name"
        assert fn.field_type == "text"
        assert fn.required is True
        assert fn.classification == FieldCategory.IDENTITY_AND_CONTACT
        assert fn.policy == PolicyType.AUTO
        assert fn.policy_approved is True
        assert fn.resolution_status == ResolutionStatus.RESOLVED
        assert fn.resolved_value == "Candidate"

        # Email
        em = field_map["email"]
        assert em.label == "Email"
        assert em.field_type == "email"
        assert em.required is True
        assert em.classification == FieldCategory.IDENTITY_AND_CONTACT
        assert em.policy_approved is True
        assert em.resolution_status == ResolutionStatus.RESOLVED
        assert em.resolved_value == "candidate.placeholder@example.com"

        # Notice Period (Question from form)
        np = field_map["job_application_answers_attributes_2_text_value"]
        assert "notice period" in np.label.lower()
        assert np.required is True
        # Unresolved from profile alone
        assert np.resolved_value is None
        assert np.is_resolved is False

    def test_sensitive_fields_strictly_blocked_as_never_fill(self, form_html: str, profile: ProfileSnapshot):
        """Verify password, OTP, and file upload fields are classified SENSITIVE_SECURITY and never filled."""
        fields = parse_greenhouse_form_html(form_html, profile=profile)
        field_map = {f.field_id: f for f in fields}

        # Password
        pw = field_map["account_password"]
        assert pw.classification == FieldCategory.SENSITIVE_SECURITY
        assert pw.policy == PolicyType.NEVER_FILL
        assert pw.resolution_status == ResolutionStatus.POLICY_BLOCKED
        assert pw.policy_approved is False
        assert pw.resolved_value is None

        # OTP
        otp = field_map["otp_verification"]
        assert otp.classification == FieldCategory.SENSITIVE_SECURITY
        assert otp.policy == PolicyType.NEVER_FILL
        assert otp.resolution_status == ResolutionStatus.POLICY_BLOCKED
        assert otp.policy_approved is False
        assert otp.resolved_value is None

        # Resume file upload
        resume = field_map["resume"]
        assert resume.classification == FieldCategory.SENSITIVE_SECURITY
        assert resume.policy == PolicyType.NEVER_FILL
        assert resume.resolution_status == ResolutionStatus.POLICY_BLOCKED
        assert resume.policy_approved is False
        assert resume.resolved_value is None

    @pytest.mark.asyncio
    async def test_answer_resolver_integration_with_policy_approval(
        self,
        form_html: str,
        profile: ProfileSnapshot,
        answer_repo: InMemoryAnswerBankRepository,
    ):
        """Verify policy approval is mandatory: matching answer with ALWAYS_ASK is not auto-approved."""
        engine = PolicyEngine()
        resolver = AnswerResolver(repository=answer_repo, policy_engine=engine)

        # 1. Add Answer Bank entry for notice period with policy ALWAYS_ASK
        entry_always_ask = AnswerBankEntry(
            key="notice_period_days",
            category="compensation_availability",
            aliases=["notice period", "What is your current notice period in days?"],
            type=AnswerType.NUMBER,
            value=30,
            policy=PolicyType.ALWAYS_ASK,
            source=AnswerSource.USER,
        )
        answer_repo.add(entry_always_ask)

        fields = parse_greenhouse_form_html(
            form_html,
            profile=profile,
            answer_resolver=resolver,
            policy_engine=engine,
        )
        field_map = {f.field_id: f for f in fields}
        np = field_map["job_application_answers_attributes_2_text_value"]

        # Even though a matching answer value (30) exists, policy ALWAYS_ASK prevents auto-approval
        assert np.policy == PolicyType.ALWAYS_ASK
        assert np.policy_approved is False
        assert np.resolution_status == ResolutionStatus.NEEDS_USER_INPUT

        # 2. Update Answer Bank entry to policy AUTO
        entry_auto = AnswerBankEntry(
            key="notice_period_days",
            category="compensation_availability",
            aliases=["notice period", "What is your current notice period in days?"],
            type=AnswerType.NUMBER,
            value=30,
            policy=PolicyType.AUTO,
            source=AnswerSource.USER,
        )
        answer_repo.update(entry_auto)

        fields2 = parse_greenhouse_form_html(
            form_html,
            profile=profile,
            answer_resolver=resolver,
            policy_engine=engine,
        )
        np2 = {f.field_id: f for f in fields2}["job_application_answers_attributes_2_text_value"]
        assert np2.policy_approved is True
        assert np2.resolution_status == ResolutionStatus.RESOLVED
        assert np2.resolved_value == 30

    def test_unknown_custom_questions_remain_unresolved(self, form_html: str, profile: ProfileSnapshot):
        """Verify unknown custom questions ('Why are you interested in joining...') fail closed."""
        fields = parse_greenhouse_form_html(form_html, profile=profile)
        field_map = {f.field_id: f for f in fields}

        why_join = field_map["job_application_answers_attributes_3_text_value"]
        assert why_join.field_type == "textarea"
        assert why_join.is_resolved is False
        assert why_join.resolved_value is None
        assert why_join.resolution_status in (ResolutionStatus.NEEDS_USER_INPUT, ResolutionStatus.NO_MATCH)

    @pytest.mark.asyncio
    async def test_provider_inspect_and_fill_returns_discovered_fields(
        self,
        profile: ProfileSnapshot,
        tmp_path: Path,
    ):
        """Verify GreenhouseProvider.inspect_and_fill returns rich discovered_fields and never submits."""
        from playwright.async_api import async_playwright

        provider = GreenhouseProvider()
        fixture_path = Path("fixtures/forms/greenhouse_job.html").resolve()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(fixture_path.as_uri())

            result: FormFillResult = await provider.inspect_and_fill(
                page=page,
                profile=profile,
                dry_run=True,
                screenshot_dir=tmp_path / "evidence",
            )

            assert result.success is True
            assert result.submit_attempted is False
            assert len(result.discovered_fields) >= 10

            # Discovered fields are populated with FormField instances
            for df in result.discovered_fields:
                assert isinstance(df, FormField)
                assert df.field_id
                assert df.label
                assert df.classification is not None

            # Sensitive fields are in discovered_fields as NEVER_FILL and are NOT in fields_filled
            filled_keys_lower = " ".join(result.fields_filled.keys()).lower()
            assert "password" not in filled_keys_lower
            assert "otp" not in filled_keys_lower
            assert "resume" not in filled_keys_lower

            # Screenshot captured
            assert result.screenshot_path is not None
            assert Path(result.screenshot_path).exists()

            await browser.close()
