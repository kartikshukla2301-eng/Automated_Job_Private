"""Unit tests for Answer Bank quality analytics and the 20 Golden Questions suite (Phase 2.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 7, Section 10)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from worker.answers.models import (
    AnswerBankEntry,
    AnswerSource,
    AnswerType,
    FieldResolutionResult,
    ResolutionStatus,
)
from worker.answers.quality import (
    AnswerBankQualityReporter,
    QualityMetricsReport,
    get_canonical_golden_questions,
)
from worker.policy.taxonomy import PolicyType


def test_answer_quality_reporter_metrics():
    """Verify freshness, provenance, and match statistics calculation."""
    now = datetime.now(timezone.utc)
    entries = [
        AnswerBankEntry(
            key="user_name",
            category="personal",
            type=AnswerType.TEXT,
            value="Jane Doe",
            source=AnswerSource.USER,
            needs_review=False,
        ),
        AnswerBankEntry(
            key="years_experience",
            category="work_history",
            type=AnswerType.NUMBER,
            value=8,
            source=AnswerSource.PROFILE,
            needs_review=False,
        ),
        AnswerBankEntry(
            key="old_salary",
            category="compensation",
            type=AnswerType.NUMBER,
            value=120000,
            source=AnswerSource.USER,
            needs_review=False,
            last_confirmed_at=now - timedelta(days=400),
            valid_until=now - timedelta(days=35),  # expired
        ),
        AnswerBankEntry(
            key="suggested_skill_summary",
            category="skills",
            type=AnswerType.TEXTAREA,
            value="Experienced with distributed cloud infrastructure",
            source=AnswerSource.LLM,
            needs_review=True,
        ),
    ]

    resolutions = [
        FieldResolutionResult(
            status=ResolutionStatus.RESOLVED,
            field_key="user_name",
            resolved_value="Jane Doe",
            policy=PolicyType.AUTO,
            policy_approved=True,
            audit_metadata={"match_method": "exact"},
        ),
        FieldResolutionResult(
            status=ResolutionStatus.RESOLVED,
            field_key="full_legal_name",
            resolved_value="Jane Doe",
            policy=PolicyType.AUTO,
            policy_approved=True,
            audit_metadata={"match_method": "alias"},
        ),
        FieldResolutionResult(
            status=ResolutionStatus.NEEDS_USER_INPUT,
            field_key="salary_expectation",
            policy=PolicyType.ALWAYS_ASK,
            policy_approved=False,
            reason="Sensitive compensation field requires user input",
        ),
    ]

    reporter = AnswerBankQualityReporter(entries=entries, resolutions=resolutions)
    report: QualityMetricsReport = reporter.generate_report(as_of=now)

    assert report.total_entries == 4
    assert report.user_entries == 2
    assert report.profile_entries == 1
    assert report.llm_entries == 1
    assert report.expired_entries == 1
    assert report.needs_review_entries == 1
    assert report.active_verified_entries == 2

    assert report.total_resolutions == 3
    assert report.exact_matches == 1
    assert report.alias_matches == 1
    assert report.unresolved_questions == 1
    assert report.unauthorized_llm_promotions == 0


def test_llm_entry_enforces_needs_review():
    """Verify architectural requirement: LLM sourced answers cannot have needs_review=False."""
    # When creating with source=LLM and needs_review=False, model validator forces needs_review=True
    entry = AnswerBankEntry(
        key="summary",
        category="general",
        type=AnswerType.TEXTAREA,
        value="Cloud architect with 8 years experience",
        source=AnswerSource.LLM,
        needs_review=False,
    )
    assert entry.needs_review is True


def test_golden_questions_fail_closed_suite():
    """Verify that all 20 canonical sensitive questions fail closed to ALWAYS_ASK / human input."""
    questions = get_canonical_golden_questions()
    assert len(questions) == 20

    def mock_resolver(field_id: str, label: str, policy: PolicyType, field_type: str) -> FieldResolutionResult:
        # In a safe system, any question with PolicyType.ALWAYS_ASK returns NEEDS_USER_INPUT or requires approval
        return FieldResolutionResult(
            status=ResolutionStatus.NEEDS_USER_INPUT,
            field_key=field_id,
            resolved_value=None,
            policy=policy,
            policy_approved=False,
            reason=f"Question '{label}' belongs to sensitive category and requires manual confirmation.",
        )

    suite_report = AnswerBankQualityReporter.evaluate_golden_questions(mock_resolver)

    assert suite_report.total_questions == 20
    assert suite_report.passed_count == 20
    assert suite_report.failed_count == 0
    assert suite_report.all_failed_closed is True
    assert len(suite_report.results) == 20

    for res in suite_report.results:
        assert res.safe_fail_closed is True
        assert res.expected_policy == PolicyType.ALWAYS_ASK
