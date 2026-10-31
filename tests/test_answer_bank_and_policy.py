"""Deterministic unit and integration tests for Answer Bank and Policy Engine (Phase 1.0).

Verifies:
1. Strongly typed AnswerBankEntry models and validation rules.
2. AnswerBankRepository protocol and InMemoryAnswerBankRepository behavior.
3. Deterministic answer resolution pipeline (exact -> alias -> variant -> miss).
4. Normalization safety (no unsafe matches between semantically different questions).
5. Expiry handling, ambiguous matches, and needs_review enforcement.
6. Centralized PolicyEngine taxonomy, code enforcement, and fail-closed defaults.
7. Sensitive security field blocking (never_fill; no overrides allowed).
8. Audit metadata generation and sensitive value redaction.
9. GreenhouseProvider integration and WalkingSkeleton regression prevention.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from worker.answers import (
    AmbiguousAnswerError,
    AnswerBankEntry,
    AnswerBankError,
    AnswerResolver,
    AnswerSource,
    AnswerType,
    FieldResolutionResult,
    InMemoryAnswerBankRepository,
    InvalidAnswerEntryError,
    PolicyViolationError,
    ResolutionStatus,
    build_audit_metadata,
    normalize_query_text,
    redact_sensitive_value,
)
from worker.core.safety import SafetyEngine
from worker.policy import (
    DEFAULT_CATEGORY_POLICIES,
    FieldCategory,
    PolicyDecision,
    PolicyEngine,
    PolicyType,
    SENSITIVE_SECURITY_KEYWORDS,
)
from worker.profile.localfile import LocalFileProfileSource
from worker.profile.models import CandidateDetails, ProfileSnapshot
from worker.providers.greenhouse import GreenhouseProvider


# ==============================================================================
# 1. Answer Bank Model Validation Tests
# ==============================================================================


def test_answer_bank_entry_valid():
    """Verify creation of a valid AnswerBankEntry with defaults."""
    entry = AnswerBankEntry(
        key="notice_period_days",
        category="availability",
        aliases=["notice period", "joining time"],
        variants=["How soon can you join?"],
        type=AnswerType.NUMBER,
        value=30,
        policy=PolicyType.AUTO_LOG,
        source=AnswerSource.USER,
        confidence=1.0,
    )
    assert entry.key == "notice_period_days"
    assert entry.category == "availability"
    assert entry.value == 30
    assert entry.policy == PolicyType.AUTO_LOG
    assert entry.needs_review is False
    assert entry.is_verified() is True
    assert entry.is_expired() is False


def test_answer_bank_entry_rejects_empty_key():
    """Verify rejection of empty or whitespace key."""
    with pytest.raises(ValueError, match="cannot be empty or whitespace"):
        AnswerBankEntry(
            key="   ",
            category="availability",
            value="30",
        )


def test_answer_bank_entry_llm_source_forces_needs_review():
    """Verify architectural rule: source=llm always forces needs_review=True."""
    entry = AnswerBankEntry(
        key="project_summary",
        category="experience",
        value="Led backend migration",
        source=AnswerSource.LLM,
        needs_review=False,  # Attempting to set false
    )
    assert entry.needs_review is True
    assert entry.is_verified() is False


def test_answer_bank_entry_invalid_number_value():
    """Verify that type=number rejects non-numeric string values."""
    with pytest.raises(ValueError, match="cannot be parsed as a number"):
        AnswerBankEntry(
            key="years_experience",
            category="experience",
            type=AnswerType.NUMBER,
            value="five years",  # Not a numeric float
        )


def test_answer_bank_entry_invalid_boolean_value():
    """Verify that type=boolean rejects non-boolean values."""
    with pytest.raises(ValueError, match="cannot be parsed as a boolean"):
        AnswerBankEntry(
            key="authorized_to_work",
            category="work_authorization",
            type=AnswerType.BOOLEAN,
            value="maybe",
        )


def test_answer_bank_entry_valid_until_before_confirmed_rejected():
    """Verify valid_until cannot precede last_confirmed_at."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(days=10)
    with pytest.raises(ValueError, match="valid_until cannot be earlier than last_confirmed_at"):
        AnswerBankEntry(
            key="expected_ctc",
            category="compensation",
            value="150000",
            last_confirmed_at=now,
            valid_until=past,
        )


def test_answer_bank_entry_forbids_extra_fields():
    """Verify strict model schema forbidding undeclared fields."""
    with pytest.raises(ValueError):
        AnswerBankEntry(
            key="test_key",
            category="test",
            value="val",
            hallucinated_field="invalid",
        )


# ==============================================================================
# 2. Repository Protocol & InMemory Implementation Tests
# ==============================================================================


def test_in_memory_repository_crud_and_scoping():
    """Verify repository add, get, update, list_by_scope, and mark_needs_review."""
    repo = InMemoryAnswerBankRepository()

    global_entry = AnswerBankEntry(
        key="notice_period_days",
        category="availability",
        value=30,
        scope="global",
        aliases=["notice period"],
    )
    company_entry = AnswerBankEntry(
        key="notice_period_days",
        category="availability",
        value=15,
        scope="company:google",
        aliases=["google notice"],
    )

    repo.add(global_entry)
    repo.add(company_entry)

    # Retrieval by scope
    assert repo.get("notice_period_days", scope="global").value == 30
    assert repo.get("notice_period_days", scope="company:google").value == 15
    assert repo.get("notice_period_days", scope="company:other") is None

    # Search by alias
    alias_matches = repo.search_by_alias("notice period")
    assert len(alias_matches) == 1
    assert alias_matches[0].value == 30

    # Scope listing
    assert len(repo.list_by_scope("global")) == 1
    assert len(repo.list_by_scope("company:google")) == 1

    # Update entry
    updated = global_entry.model_copy(update={"value": 45})
    repo.update(updated)
    assert repo.get("notice_period_days", scope="global").value == 45

    # Mark needs review
    repo.mark_needs_review("notice_period_days", scope="global")
    entry_after_review = repo.get("notice_period_days", scope="global")
    assert entry_after_review.needs_review is True


def test_in_memory_repository_empty_key_rejected():
    """Verify that adding an entry with empty key raises InvalidAnswerEntryError."""
    repo = InMemoryAnswerBankRepository()
    # Construct invalid object via private dict or model bypass
    with pytest.raises(InvalidAnswerEntryError):
        # Create a mock entry with empty key
        class MockEntry:
            key = ""
            scope = "global"
        repo.add(MockEntry())  # type: ignore


# ==============================================================================
# 3. Deterministic Answer Resolution Pipeline Tests
# ==============================================================================


@pytest.fixture
def populated_repository() -> InMemoryAnswerBankRepository:
    repo = InMemoryAnswerBankRepository()
    repo.add(
        AnswerBankEntry(
            key="notice_period_days",
            category="availability",
            aliases=["notice period", "joining time"],
            variants=["How soon can you join?", "What is your notice period?"],
            type=AnswerType.NUMBER,
            value=30,
            option_mapping={"<=15": "Immediate", "<=30": "1 Month"},
            policy=PolicyType.AUTO_LOG,
            scope="global",
            last_confirmed_at=datetime.now(timezone.utc),
            valid_until=datetime.now(timezone.utc) + timedelta(days=60),
        )
    )
    repo.add(
        AnswerBankEntry(
            key="notice_period_days",
            category="availability",
            value=15,
            policy=PolicyType.AUTO_LOG,
            scope="company:startup_inc",
            last_confirmed_at=datetime.now(timezone.utc),
        )
    )
    repo.add(
        AnswerBankEntry(
            key="work_authorization",
            category="work_authorization",
            aliases=["authorized to work", "legally authorized"],
            type=AnswerType.BOOLEAN,
            value=True,
            policy=PolicyType.AUTO_LOG,
            scope="global",
        )
    )
    repo.add(
        AnswerBankEntry(
            key="expected_ctc",
            category="compensation",
            aliases=["expected salary"],
            type=AnswerType.NUMBER,
            value=160000,
            policy=PolicyType.ALWAYS_ASK,
            scope="global",
        )
    )
    return repo


def test_resolver_exact_key_matching(populated_repository: InMemoryAnswerBankRepository):
    """Verify exact key matching directly retrieves verified answer."""
    engine = PolicyEngine()
    resolver = AnswerResolver(repository=populated_repository, policy_engine=engine)

    result = resolver.resolve_field("notice_period_days")
    assert result.status == ResolutionStatus.RESOLVED
    assert result.resolved_value == 30
    assert result.policy == PolicyType.AUTO_LOG
    assert result.policy_approved is True
    assert result.audit_metadata["resolution_method"] == "exact_key"


def test_resolver_scope_hierarchy_precedence(populated_repository: InMemoryAnswerBankRepository):
    """Verify company scope takes precedence over global, and falls back to global."""
    engine = PolicyEngine()
    resolver = AnswerResolver(repository=populated_repository, policy_engine=engine)

    # Scoped match
    result_company = resolver.resolve_field("notice_period_days", scope="company:startup_inc")
    assert result_company.status == ResolutionStatus.RESOLVED
    assert result_company.resolved_value == 15

    # Global fallback for field without company override
    result_fallback = resolver.resolve_field("work_authorization", scope="company:startup_inc")
    assert result_fallback.status == ResolutionStatus.RESOLVED
    assert result_fallback.resolved_value is True
    assert result_fallback.audit_metadata["resolution_method"] == "exact_key_global_fallback"


def test_resolver_alias_and_variant_normalization(populated_repository: InMemoryAnswerBankRepository):
    """Verify alias and variant matching with punctuation and whitespace normalization."""
    engine = PolicyEngine()
    resolver = AnswerResolver(repository=populated_repository, policy_engine=engine)

    # Match by alias with trailing punctuation and mixed casing
    res_alias = resolver.resolve_field(
        field_key="custom_q1",
        label_text="  Notice  Period:? ",
    )
    assert res_alias.status == ResolutionStatus.RESOLVED
    assert res_alias.resolved_value == 30

    # Match by question variant
    res_variant = resolver.resolve_field(
        field_key="custom_q2",
        label_text="How soon can you join?",
    )
    assert res_variant.status == ResolutionStatus.RESOLVED
    assert res_variant.resolved_value == 30


def test_normalization_safety_prevents_unsafe_cross_matching():
    """Verify normalization does NOT match semantically distinct fields."""
    repo = InMemoryAnswerBankRepository()
    repo.add(
        AnswerBankEntry(
            key="first_name",
            category="identity_and_contact",
            aliases=["first name"],
            value="Kartik",
            policy=PolicyType.AUTO,
        )
    )
    repo.add(
        AnswerBankEntry(
            key="last_name",
            category="identity_and_contact",
            aliases=["last name"],
            value="Shukla",
            policy=PolicyType.AUTO,
        )
    )
    resolver = AnswerResolver(repository=repo, policy_engine=PolicyEngine())

    # "first_name" must NOT match "last name"
    res1 = resolver.resolve_field("first_name", label_text="Last Name")
    assert res1.resolved_value != "Shukla"
    res2 = resolver.resolve_field("last_name", label_text="First Name")
    assert res2.resolved_value != "Kartik"


def test_resolver_ambiguous_matches_fail_closed():
    """Verify multiple conflicting answers for the same query return AMBIGUOUS status."""
    repo = InMemoryAnswerBankRepository()
    repo.add(
        AnswerBankEntry(
            key="pref_loc_1",
            category="work_preferences",
            aliases=["preferred location"],
            value="San Francisco",
            policy=PolicyType.AUTO_LOG,
        )
    )
    repo.add(
        AnswerBankEntry(
            key="pref_loc_2",
            category="work_preferences",
            aliases=["preferred location"],
            value="New York",
            policy=PolicyType.AUTO_LOG,
        )
    )
    resolver = AnswerResolver(repository=repo, policy_engine=PolicyEngine())

    res = resolver.resolve_field("location", label_text="Preferred Location")
    assert res.status == ResolutionStatus.AMBIGUOUS
    assert res.policy_approved is False
    assert "multiple distinct answers found" in res.reason


def test_resolver_expired_answer_fails_closed():
    """Verify answer records past valid_until return EXPIRED status and require user review."""
    repo = InMemoryAnswerBankRepository()
    now = datetime.now(timezone.utc)
    expired_time = now - timedelta(days=2)

    repo.add(
        AnswerBankEntry(
            key="availability_date",
            category="availability",
            value="2026-10-01",
            policy=PolicyType.AUTO_LOG,
            last_confirmed_at=now - timedelta(days=90),
            valid_until=expired_time,
        )
    )
    resolver = AnswerResolver(repository=repo, policy_engine=PolicyEngine())

    res = resolver.resolve_field("availability_date")
    assert res.status == ResolutionStatus.EXPIRED
    assert res.policy_approved is False
    assert res.resolved_value is None
    assert "expired" in res.reason.lower()


def test_resolver_needs_review_forces_user_input():
    """Verify answer records marked with needs_review=True return NEEDS_USER_INPUT."""
    repo = InMemoryAnswerBankRepository()
    repo.add(
        AnswerBankEntry(
            key="ai_drafted_summary",
            category="experience",
            value="Summary generated by LLM",
            policy=PolicyType.AUTO,
            source=AnswerSource.LLM,
            needs_review=True,
        )
    )
    resolver = AnswerResolver(repository=repo, policy_engine=PolicyEngine())

    res = resolver.resolve_field("ai_drafted_summary")
    assert res.status == ResolutionStatus.NEEDS_USER_INPUT
    assert res.policy_approved is False
    assert "user review" in res.reason.lower()


def test_resolver_no_match_returns_no_match():
    """Verify unanswerable questions return NO_MATCH without fabricating candidate data."""
    repo = InMemoryAnswerBankRepository()
    resolver = AnswerResolver(repository=repo, policy_engine=PolicyEngine())

    res = resolver.resolve_field("unknown_custom_question", label_text="What was your favorite high school course?")
    assert res.status == ResolutionStatus.NO_MATCH
    assert res.resolved_value is None
    assert res.policy_approved is False


def test_resolver_dropdown_option_mapping(populated_repository: InMemoryAnswerBankRepository):
    """Verify dropdown option mapping against available_options."""
    engine = PolicyEngine()
    resolver = AnswerResolver(repository=populated_repository, policy_engine=engine)

    # 1. Successful option mapping
    res_success = resolver.resolve_field(
        "notice_period_days",
        available_options=["Immediate", "1 Month", "2 Months", "3 Months"],
    )
    assert res_success.status == ResolutionStatus.RESOLVED
    assert res_success.resolved_value == "1 Month"
    assert res_success.applied_option == "1 Month"

    # 2. Form lacks the mapped option -> returns NEEDS_USER_INPUT
    res_missing_opt = resolver.resolve_field(
        "notice_period_days",
        available_options=["Under 2 weeks", "Over 60 days"],
    )
    assert res_missing_opt.status == ResolutionStatus.NEEDS_USER_INPUT
    assert res_missing_opt.policy_approved is False


# ==============================================================================
# 4. Policy Engine Taxonomy and Code Enforcement Tests
# ==============================================================================


def test_policy_engine_all_policies_enforced():
    """Verify that every policy type produces strictly correct decision flags."""
    engine = PolicyEngine()

    # AUTO: identity
    d_auto = engine.evaluate("first_name", "First Name")
    assert d_auto.policy == PolicyType.AUTO
    assert d_auto.allowed is True
    assert d_auto.requires_logging is False
    assert d_auto.requires_user_approval is False
    assert d_auto.is_blocked is False

    # AUTO_LOG: availability
    d_autolog = engine.evaluate("notice_period", "Notice Period")
    assert d_autolog.policy == PolicyType.AUTO_LOG
    assert d_autolog.allowed is True
    assert d_autolog.requires_logging is True
    assert d_autolog.requires_user_approval is False
    assert d_autolog.is_blocked is False

    # ALWAYS_ASK: compensation
    d_ask = engine.evaluate("expected_salary", "Expected Salary")
    assert d_ask.policy == PolicyType.ALWAYS_ASK
    assert d_ask.allowed is False
    assert d_ask.requires_user_approval is True
    assert d_ask.is_blocked is False

    # NEVER_FILL: passwords, SSN
    d_block = engine.evaluate("password", "Enter Password")
    assert d_block.policy == PolicyType.NEVER_FILL
    assert d_block.allowed is False
    assert d_block.is_blocked is True


def test_policy_engine_unknown_field_defaults_to_always_ask():
    """Verify that unclassified fields default to UNKNOWN_UNCLASSIFIED and always_ask (fail closed)."""
    engine = PolicyEngine()
    decision = engine.evaluate("weird_custom_attr_99", "Describe an unusual hobby")
    assert decision.category == FieldCategory.UNKNOWN_UNCLASSIFIED
    assert decision.policy == PolicyType.ALWAYS_ASK
    assert decision.allowed is False
    assert decision.requires_user_approval is True


def test_policy_engine_sensitive_security_cannot_be_overridden():
    """Verify that sensitive security fields cannot be loosened by custom policies or entry hints."""
    # Attempting to override SENSITIVE_SECURITY in constructor raises PolicyViolationError
    with pytest.raises(PolicyViolationError):
        PolicyEngine(custom_category_policies={FieldCategory.SENSITIVE_SECURITY: PolicyType.AUTO})

    # Explicit policy on evaluate cannot loosen SENSITIVE_SECURITY
    engine = PolicyEngine()
    decision = engine.evaluate("ssn", "Social Security Number", explicit_policy="auto")
    assert decision.category == FieldCategory.SENSITIVE_SECURITY
    assert decision.policy == PolicyType.NEVER_FILL
    assert decision.is_blocked is True


def test_policy_engine_comprehensive_sensitive_security_keywords():
    """Verify all defined sensitive security keywords trigger NEVER_FILL."""
    engine = PolicyEngine()
    test_cases = [
        "account_number",
        "routing_number",
        "ssn",
        "national_id",
        "passport",
        "bank_name",
        "otp_code",
        "verification_code",
        "security_code",
        "recaptcha_response",
        "turnstile",
        "password",
        "drivers_license",
    ]
    for kw in test_cases:
        decision = engine.evaluate(kw)
        assert decision.category == FieldCategory.SENSITIVE_SECURITY, f"Failed for keyword: {kw}"
        assert decision.policy == PolicyType.NEVER_FILL, f"Failed policy for keyword: {kw}"
        assert decision.is_blocked is True


# ==============================================================================
# 5. Audit & Redaction Tests
# ==============================================================================


def test_audit_redaction_masks_sensitive_values():
    """Verify that audit formatting masks sensitive values."""
    assert redact_sensitive_value("salary", "150000") == "[REDACTED]"
    assert redact_sensitive_value("compensation_expectation", "200000") == "[REDACTED]"
    assert redact_sensitive_value("bank_account", "123456789") == "[REDACTED]"
    assert redact_sensitive_value("user_password", "Secret!23") == "[REDACTED]"
    assert redact_sensitive_value("first_name", "Kartik") == "Kartik"

    # Verify build_audit_metadata structure
    meta = build_audit_metadata(
        field_key="expected_salary",
        resolution_method="exact_key",
        policy_applied="always_ask",
        result_status="RESOLVED",
        reason="Answer resolved",
        raw_value="180000",
    )
    assert meta["redacted_value"] == "[REDACTED]"
    assert meta["field_key"] == "expected_salary"
    assert "timestamp" in meta


# ==============================================================================
# 6. Profile Fallback and Greenhouse Provider Integration Tests
# ==============================================================================


@pytest.fixture
def test_profile_snapshot() -> ProfileSnapshot:
    source = LocalFileProfileSource("fixtures/profile.yaml")
    return source.load_snapshot()


def test_resolver_with_profile_fallback(
    populated_repository: InMemoryAnswerBankRepository,
    test_profile_snapshot: ProfileSnapshot,
):
    """Verify resolver extracts verified candidate facts when Answer Bank lacks entry."""
    engine = PolicyEngine()
    resolver = AnswerResolver(repository=populated_repository, policy_engine=engine)

    # Email is in profile, not Answer Bank
    res = resolver.resolve_with_profile_fallback(
        field_key="email",
        label_text="Email Address",
        profile=test_profile_snapshot,
    )
    assert res.status == ResolutionStatus.RESOLVED
    assert res.resolved_value == test_profile_snapshot.candidate.email
    assert res.policy_approved is True
    assert res.audit_metadata["resolution_method"] == "profile_snapshot"


def test_greenhouse_provider_uses_answer_resolver(
    populated_repository: InMemoryAnswerBankRepository,
    test_profile_snapshot: ProfileSnapshot,
):
    """Verify GreenhouseProvider interacts seamlessly with AnswerResolver and PolicyEngine."""
    engine = PolicyEngine()
    resolver = AnswerResolver(repository=populated_repository, policy_engine=engine)
    provider = GreenhouseProvider(answer_resolver=resolver, policy_engine=engine)

    # 1. Standard name from profile fallback
    first_name = provider.resolve_field("First Name", "first_name", test_profile_snapshot)
    assert first_name == test_profile_snapshot.candidate.name.split()[0]

    # 2. Answer Bank availability question
    notice = provider.resolve_field("Notice Period", "notice_period", test_profile_snapshot)
    assert notice == "30"

    # 3. Sensitive question is blocked
    pwd = provider.resolve_field("Password", "job_application_password", test_profile_snapshot)
    assert pwd is None

    # 4. Unknown question fails closed
    unknown = provider.resolve_field("Favorite Animal", "fav_animal", test_profile_snapshot)
    assert unknown is None
