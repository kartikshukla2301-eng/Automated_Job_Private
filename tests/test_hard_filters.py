"""Comprehensive unit tests for deterministic hard eligibility filters.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from worker.discovery.models import Job, JobStatus, SalaryInfo
from worker.matching.hard_filters import evaluate_hard_filters, extract_min_experience_years
from worker.matching.models import CandidateJobPreferences


@pytest.fixture
def base_preferences() -> CandidateJobPreferences:
    return CandidateJobPreferences(
        roles=["Software Engineer", "Backend Engineer"],
        locations=["Bengaluru", "San Francisco"],
        work_modes=["remote", "hybrid"],
        levels=["junior", "mid"],
        employment_types=["full-time"],
        min_salary=80000.0,
        currency="USD",
        blocklisted_companies=["EvilCorp", "Spam Inc"],
        blocklisted_keywords=["crypto", "unpaid"],
        max_job_age_hours=24,
        max_experience_years=3.0,
    )


@pytest.fixture
def valid_job() -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        platform="greenhouse",
        external_id="gh-12345",
        canonical_key="acme_corp:software_engineer:remote",
        company="Acme Corp",
        normalized_company="acme corp",
        title="Software Engineer",
        normalized_title="software engineer",
        url="https://boards.greenhouse.io/acmepay/jobs/12345",
        description="We are looking for a Software Engineer with Python and React skills.",
        location="Remote",
        location_bucket="remote",
        employment_type="Full-time",
        experience_requirements="1-3 years",
        salary=SalaryInfo(min_amount=90000.0, max_amount=120000.0, currency="USD", interval="yearly"),
        posted_at=now - timedelta(hours=2),
        first_seen_at=now - timedelta(hours=2),
        content_hash="a" * 64,
        status=JobStatus.DISCOVERED,
    )


def test_hard_filter_allows_valid_job(valid_job, base_preferences):
    res = evaluate_hard_filters(valid_job, base_preferences)
    assert res.passed is True
    assert len(res.reasons) == 0


def test_hard_filter_rejects_closed_status(valid_job, base_preferences):
    for status in [JobStatus.EXPIRED, JobStatus.REJECTED, JobStatus.IGNORED, JobStatus.DUPLICATE]:
        job = valid_job.model_copy(update={"status": status})
        res = evaluate_hard_filters(job, base_preferences)
        assert res.passed is False
        assert any("not open for application" in r for r in res.reasons)


def test_hard_filter_rejects_stale_job_exceeding_max_age(valid_job, base_preferences):
    now = datetime.now(timezone.utc)
    stale_job = valid_job.model_copy(update={"posted_at": now - timedelta(hours=30)})
    res = evaluate_hard_filters(stale_job, base_preferences, now=now)
    assert res.passed is False
    assert any("exceeds maximum allowed age" in r for r in res.reasons)


def test_hard_filter_allows_job_without_posted_date_using_first_seen(valid_job, base_preferences):
    now = datetime.now(timezone.utc)
    job = valid_job.model_copy(update={"posted_at": None, "first_seen_at": now - timedelta(hours=1)})
    res = evaluate_hard_filters(job, base_preferences, now=now)
    assert res.passed is True


def test_hard_filter_rejects_duplicate_or_already_applied(valid_job, base_preferences):
    # Test UUID match
    res1 = evaluate_hard_filters(valid_job, base_preferences, applied_job_ids={str(valid_job.id)})
    assert res1.passed is False
    assert any("already been applied" in r for r in res1.reasons)

    # Test external_id match
    res2 = evaluate_hard_filters(valid_job, base_preferences, applied_job_ids={valid_job.external_id})
    assert res2.passed is False

    # Test canonical_key match
    res3 = evaluate_hard_filters(valid_job, base_preferences, applied_job_ids={valid_job.canonical_key})
    assert res3.passed is False


def test_hard_filter_rejects_blocklisted_company(valid_job, base_preferences):
    job = valid_job.model_copy(update={"company": "EvilCorp LLC", "normalized_company": "evilcorp"})
    res = evaluate_hard_filters(job, base_preferences)
    assert res.passed is False
    assert any("in candidate blocklist" in r for r in res.reasons)


def test_hard_filter_rejects_blocklisted_keywords_in_title(valid_job, base_preferences):
    job = valid_job.model_copy(update={"title": "Crypto Backend Developer"})
    res = evaluate_hard_filters(job, base_preferences)
    assert res.passed is False
    assert any("blocklisted keyword 'crypto'" in r for r in res.reasons)


def test_hard_filter_rejects_blocklisted_keywords_in_description(valid_job, base_preferences):
    job = valid_job.model_copy(update={"description": "This is an unpaid internship position."})
    res = evaluate_hard_filters(job, base_preferences)
    assert res.passed is False
    assert any("blocklisted keyword 'unpaid'" in r for r in res.reasons)


def test_hard_filter_cooldown_rejects_within_30_days(valid_job, base_preferences):
    now = datetime.now(timezone.utc)
    cooldowns = {"acme corp": now - timedelta(days=15)}
    res = evaluate_hard_filters(valid_job, base_preferences, applied_company_cooldowns=cooldowns, now=now)
    assert res.passed is False
    assert any("in cooldown" in r for r in res.reasons)


def test_hard_filter_cooldown_allows_after_30_days(valid_job, base_preferences):
    now = datetime.now(timezone.utc)
    cooldowns = {"acme corp": now - timedelta(days=31)}
    res = evaluate_hard_filters(valid_job, base_preferences, applied_company_cooldowns=cooldowns, now=now)
    assert res.passed is True


def test_hard_filter_daily_company_cap(valid_job, base_preferences):
    counts = {"acme corp": 2}
    res = evaluate_hard_filters(valid_job, base_preferences, applied_company_counts_today=counts)
    assert res.passed is False
    assert any("daily application cap" in r for r in res.reasons)


def test_hard_filter_remote_only_rejects_onsite(valid_job):
    prefs = CandidateJobPreferences(work_modes=["remote"])
    onsite_job = valid_job.model_copy(update={"location_bucket": "onsite", "location": "New York, NY"})
    res = evaluate_hard_filters(onsite_job, prefs)
    assert res.passed is False
    assert any("candidate strictly requires remote work" in r.lower() for r in res.reasons)


def test_hard_filter_missing_location_does_not_reject(valid_job):
    prefs = CandidateJobPreferences(locations=["Bengaluru"])
    job = valid_job.model_copy(update={"location": None, "location_bucket": None})
    res = evaluate_hard_filters(job, prefs)
    assert res.passed is True
    assert "location" in res.missing_fields


def test_hard_filter_rejects_mismatched_employment_type(valid_job):
    prefs = CandidateJobPreferences(employment_types=["full-time"])
    contract_job = valid_job.model_copy(update={"employment_type": "Contract / Freelance"})
    res = evaluate_hard_filters(contract_job, prefs)
    assert res.passed is False
    assert any("employment type" in r.lower() for r in res.reasons)


def test_hard_filter_missing_employment_type_does_not_reject(valid_job):
    prefs = CandidateJobPreferences(employment_types=["full-time"])
    job = valid_job.model_copy(update={"employment_type": None})
    res = evaluate_hard_filters(job, prefs)
    assert res.passed is True
    assert "employment_type" in res.missing_fields


def test_hard_filter_junior_ceiling_rejects_senior_title(valid_job):
    prefs = CandidateJobPreferences(levels=["junior", "fresher"], max_experience_years=2.0)
    senior_job = valid_job.model_copy(update={"title": "Staff Principal Engineer", "experience_requirements": None})
    res = evaluate_hard_filters(senior_job, prefs)
    assert res.passed is False
    assert any("senior role" in r.lower() for r in res.reasons)


def test_hard_filter_experience_years_ceiling_rejects_higher_requirement(valid_job):
    prefs = CandidateJobPreferences(max_experience_years=2.0)
    senior_job = valid_job.model_copy(update={"experience_requirements": "5+ years required"})
    res = evaluate_hard_filters(senior_job, prefs)
    assert res.passed is False
    assert any("exceeding candidate ceiling" in r.lower() for r in res.reasons)


def test_hard_filter_salary_rejects_below_minimum(valid_job):
    prefs = CandidateJobPreferences(min_salary=100000.0, currency="USD")
    low_paying_job = valid_job.model_copy(
        update={"salary": SalaryInfo(min_amount=60000.0, max_amount=80000.0, currency="USD")}
    )
    res = evaluate_hard_filters(low_paying_job, prefs)
    assert res.passed is False
    assert any("below minimum requirement" in r.lower() for r in res.reasons)


def test_hard_filter_missing_salary_does_not_reject(valid_job):
    prefs = CandidateJobPreferences(min_salary=100000.0, currency="USD")
    no_salary_job = valid_job.model_copy(update={"salary": None})
    res = evaluate_hard_filters(no_salary_job, prefs)
    assert res.passed is True
    assert "salary" in res.missing_fields


def test_extract_min_experience_years():
    assert extract_min_experience_years("3+ years of experience") == 3.0
    assert extract_min_experience_years("Requires 5-7 years experience") == 5.0
    assert extract_min_experience_years("Minimum 2 to 4 years experience") == 2.0
    assert extract_min_experience_years("No requirements listed") is None
    assert extract_min_experience_years(None) is None
