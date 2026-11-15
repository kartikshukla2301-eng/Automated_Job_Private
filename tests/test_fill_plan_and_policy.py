"""Tests for FillPlan compilation, Answer Bank mapping, and PolicyEngine enforcement.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 7, 8, 11)
- docs/BUILD_RULES.md
"""

import asyncio
from pathlib import Path
from uuid import uuid4
import pytest

from worker.answers.models import AnswerBankEntry
from worker.answers.repository import InMemoryAnswerBankRepository
from worker.answers.resolver import AnswerResolver
from worker.browser.browser_session import BrowserSession
from worker.browser.execution_context import ExecutionContext
from worker.browser.field_detector import DetectedField
from worker.browser.fill_plan import FillPlan, PlannedField, ResolutionOutcome
from worker.policy.engine import PolicyEngine
from worker.policy.taxonomy import FieldCategory, PolicyType
from worker.profile.localfile import LocalFileProfileSource
from worker.profile.models import ProfileSnapshot


@pytest.fixture
def profile_snapshot() -> ProfileSnapshot:
    source = LocalFileProfileSource(Path("fixtures/profile.yaml"))
    return asyncio.run(source.get_snapshot())


@pytest.fixture
def answer_repo() -> InMemoryAnswerBankRepository:
    repo = InMemoryAnswerBankRepository()
    repo.add(
        AnswerBankEntry(
            key="notice_period",
            category=FieldCategory.AVAILABILITY.value,
            aliases=["notice period", "notice_period"],
            variants=["how soon can you start", "What is your notice period in days? *"],
            value="30 days",
            confidence=0.95,
            needs_review=False,
            policy=PolicyType.AUTO,
        )
    )
    repo.add(
        AnswerBankEntry(
            key="unverified_reason",
            category=FieldCategory.MOTIVATION_COVER_LETTER.value,
            aliases=["why do you want to work here", "why_join"],
            variants=["Why do you want to work here?"],
            value="Excited about the tech stack",
            confidence=0.7,
            needs_review=True,
            policy=PolicyType.ALWAYS_ASK,
        )
    )
    return repo


@pytest.fixture
def execution_context(profile_snapshot, answer_repo) -> ExecutionContext:
    session = BrowserSession(user_id=uuid4())
    policy_engine = PolicyEngine()
    resolver = AnswerResolver(repository=answer_repo, policy_engine=policy_engine)
    return ExecutionContext(
        session=session,
        answer_resolver=resolver,
        policy_engine=policy_engine,
        profile=profile_snapshot,
    )


@pytest.mark.asyncio
async def test_plan_resolves_profile_contact_info(execution_context: ExecutionContext):
    """Verify standard candidate contact info is resolved to AUTO_APPROVED."""
    fn_field = DetectedField(
        field_id="first_name",
        label="First Name *",
        name="first_name",
        tag_name="input",
        input_type="text",
        required=True,
        semantic_selector="#first_name",
        confidence=1.0,
        is_sensitive=False,
    )
    planned = execution_context._plan_field(fn_field, provider_name="greenhouse")
    assert planned.resolution_outcome == ResolutionOutcome.AUTO_APPROVED
    assert planned.field_category == FieldCategory.IDENTITY_AND_CONTACT
    assert planned.proposed_answer_ref == "profile:candidate.first_name"
    assert planned.is_safe_to_prefill is True


@pytest.mark.asyncio
async def test_plan_resolves_answer_bank_entry(execution_context: ExecutionContext):
    """Verify configured Answer Bank questions are resolved with provenance."""
    notice_field = DetectedField(
        field_id="notice_period",
        label="What is your notice period in days? *",
        name="notice_period",
        tag_name="input",
        input_type="text",
        required=True,
        semantic_selector="#notice_period",
        confidence=1.0,
        is_sensitive=False,
    )
    planned = execution_context._plan_field(notice_field, provider_name="greenhouse")
    assert planned.resolution_outcome == ResolutionOutcome.AUTO_APPROVED
    assert planned.proposed_answer_ref == "answers:notice_period"


@pytest.mark.asyncio
async def test_plan_marks_unverified_answer_needs_review(execution_context: ExecutionContext):
    """Verify answers flagged needs_review=True require human review before prefill."""
    why_field = DetectedField(
        field_id="why_join",
        label="Why do you want to work here?",
        name="why_join",
        tag_name="textarea",
        input_type="textarea",
        required=False,
        semantic_selector="#why_join",
        confidence=1.0,
        is_sensitive=False,
    )
    planned = execution_context._plan_field(why_field, provider_name="greenhouse")
    assert planned.resolution_outcome == ResolutionOutcome.NEEDS_REVIEW
    assert planned.proposed_answer_ref == "answers:unverified_reason"
    assert planned.required_user_action == "User review required."


@pytest.mark.asyncio
async def test_plan_blocks_sensitive_fields_never_fill(execution_context: ExecutionContext):
    """Verify password, OTP, and sensitive credential fields are strictly POLICY_BLOCKED."""
    pw_field = DetectedField(
        field_id="password",
        label="Create Password",
        name="password",
        tag_name="input",
        input_type="password",
        required=True,
        semantic_selector="#password",
        confidence=1.0,
        is_sensitive=True,
    )
    planned = execution_context._plan_field(pw_field, provider_name="greenhouse")
    assert planned.resolution_outcome == ResolutionOutcome.POLICY_BLOCKED
    assert planned.policy_type == PolicyType.NEVER_FILL
    assert planned.field_category == FieldCategory.SENSITIVE_SECURITY
    assert planned.proposed_answer_ref is None
    assert planned.is_safe_to_prefill is False


@pytest.mark.asyncio
async def test_plan_unresolved_missing_answer(execution_context: ExecutionContext):
    """Verify completely unknown question becomes NO_MATCH without fabrication."""
    unknown_field = DetectedField(
        field_id="custom_fav_color",
        label="What is your favorite distributed systems paper?",
        name="custom_fav_color",
        tag_name="input",
        input_type="text",
        required=True,
        semantic_selector="#custom_fav_color",
        confidence=1.0,
        is_sensitive=False,
    )
    planned = execution_context._plan_field(unknown_field, provider_name="greenhouse")
    assert planned.resolution_outcome == ResolutionOutcome.NO_MATCH
    assert planned.proposed_answer_ref is None
    assert "Mandatory field requires candidate input" in (planned.required_user_action or "")


def test_fill_plan_is_executable_logic():
    """Verify FillPlan.is_executable() returns False if any required field is unresolved."""
    field_resolved = PlannedField(
        field_id="f1",
        detected_field=DetectedField(
            field_id="f1",
            label="Email *",
            tag_name="input",
            input_type="email",
            required=True,
            semantic_selector="#email",
            is_sensitive=False,
        ),
        proposed_answer_ref="profile:candidate.email",
        resolution_outcome=ResolutionOutcome.AUTO_APPROVED,
        policy_type=PolicyType.AUTO,
        field_category=FieldCategory.IDENTITY_AND_CONTACT,
        confidence=1.0,
        explanation="Resolved",
        is_safe_to_prefill=True,
    )

    field_unresolved = PlannedField(
        field_id="f2",
        detected_field=DetectedField(
            field_id="f2",
            label="Notice Period *",
            tag_name="input",
            input_type="text",
            required=True,
            semantic_selector="#notice",
            is_sensitive=False,
        ),
        proposed_answer_ref=None,
        resolution_outcome=ResolutionOutcome.NO_MATCH,
        policy_type=PolicyType.ALWAYS_ASK,
        field_category=FieldCategory.AVAILABILITY,
        confidence=0.0,
        explanation="Missing answer",
        is_safe_to_prefill=False,
    )

    plan = FillPlan(
        session_id=uuid4(),
        canonical_url="https://boards.greenhouse.io/job",
        fields=[field_resolved, field_unresolved],
    )

    # Not executable because f2 is mandatory and unresolved
    assert plan.is_executable() is False
    unresolved_list = plan.get_unresolved_required_fields()
    assert len(unresolved_list) == 1
    assert unresolved_list[0].field_id == "f2"
