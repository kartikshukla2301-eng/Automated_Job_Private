"""Deterministic hard eligibility filters for job matching.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10)
- docs/BUILD_RULES.md
- config/config.yaml (matching, caps)

CRITICAL INVARIANTS:
1. Missing job information must NOT be invented.
2. Unknown information must be represented explicitly in missing_fields.
3. Do NOT reject a job solely because optional information is missing, unless
   architecture or candidate preferences explicitly require it.
4. Hard exclusions can NEVER be overridden by an LLM or high match score.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import List, Optional, Set

from worker.discovery.models import Job, JobStatus
from worker.discovery.normalization import normalize_company
from worker.matching.models import CandidateJobPreferences, HardFilterResult

SENIORITY_KEYWORDS_REGEX = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|director|vp|head\s+of|manager)\b",
    re.IGNORECASE,
)
EXPERIENCE_YEARS_REGEX = re.compile(
    r"(?:(\d+)(?:\.\d+)?)\s*(?:\+|-|\sto\s)\s*(?:(\d+)(?:\.\d+)?)?\s*years?",
    re.IGNORECASE,
)


def extract_min_experience_years(text: Optional[str]) -> Optional[float]:
    """Extract minimum years of required experience if explicitly stated in text."""
    if not text:
        return None
    match = EXPERIENCE_YEARS_REGEX.search(text)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, TypeError):
            return None
    return None


def evaluate_hard_filters(
    job: Job,
    preferences: CandidateJobPreferences,
    applied_company_cooldowns: Optional[dict[str, datetime]] = None,
    applied_company_counts_today: Optional[dict[str, int]] = None,
    applied_job_ids: Optional[Set[str]] = None,
    now: Optional[datetime] = None,
) -> HardFilterResult:
    """Evaluate deterministic hard eligibility constraints against a canonical job.

    Returns HardFilterResult with passed=True/False, specific rejection reasons,
    and missing/unknown fields.
    """
    reasons: List[str] = []
    missing_fields: List[str] = []
    current_time = now or datetime.now(timezone.utc)
    applied_cooldowns = applied_company_cooldowns or {}
    company_counts = applied_company_counts_today or {}
    applied_ids = applied_job_ids or set()

    norm_company = job.normalized_company or normalize_company(job.company)

    # 1. Job Lifecycle Status Check
    # Valid discovery statuses are DISCOVERED and MATCHED
    if job.status in {JobStatus.EXPIRED, JobStatus.REJECTED, JobStatus.IGNORED, JobStatus.DUPLICATE}:
        reasons.append(f"Job is not open for application (status: {job.status.value})")

    # 2. Freshness / Max Job Age Check
    effective_posted_at = job.posted_at or job.first_seen_at
    if effective_posted_at:
        # Handle naive vs aware datetimes safely
        if effective_posted_at.tzinfo is None:
            effective_posted_at = effective_posted_at.replace(tzinfo=timezone.utc)
        age_hours = (current_time - effective_posted_at).total_seconds() / 3600.0
        if age_hours > preferences.max_job_age_hours:
            reasons.append(
                f"Job posting age ({age_hours:.1f}h) exceeds maximum allowed age ({preferences.max_job_age_hours}h)"
            )
    else:
        missing_fields.append("posted_at")

    # 3. Duplicate and Already Applied Check
    job_identifiers = {str(job.id), job.external_id, job.canonical_key}
    if any(jid in applied_ids for jid in job_identifiers):
        reasons.append("Job has already been applied to or is an existing duplicate")

    # 4. Blocklisted Companies
    norm_blocklisted_companies = {normalize_company(c) for c in preferences.blocklisted_companies if c.strip()}
    if norm_company in norm_blocklisted_companies:
        reasons.append(f"Company '{job.company}' is in candidate blocklist")

    # 5. Blocklisted Keywords (Checked in title and description)
    text_corpus = f"{job.title} {job.description or ''}".lower()
    for kw in preferences.blocklisted_keywords:
        clean_kw = kw.strip().lower()
        if clean_kw and re.search(r"\b" + re.escape(clean_kw) + r"\b", text_corpus):
            reasons.append(f"Job contains blocklisted keyword '{kw}'")

    # 6. Company Cooldown & Daily Cap (Architecture Section 10 / RC-9)
    # Cooldown: 1 application per company per 30 days unless role family differs
    last_applied = applied_cooldowns.get(norm_company)
    if last_applied:
        if last_applied.tzinfo is None:
            last_applied = last_applied.replace(tzinfo=timezone.utc)
        days_since_apply = (current_time - last_applied).total_seconds() / 86400.0
        if days_since_apply < 30.0:
            reasons.append(
                f"Company '{job.company}' is in cooldown ({days_since_apply:.1f}/30 days elapsed since last application)"
            )

    # Per-company daily cap: maximum 2 applications per company per day
    if company_counts.get(norm_company, 0) >= 2:
        reasons.append(f"Company '{job.company}' reached daily application cap (2/2 today)")

    # 7. Location & Work Mode Filter
    # Missing work mode or location does NOT disqualify unless candidate strictly requires it
    pref_modes = {m.lower().strip() for m in preferences.work_modes if m.strip()}
    job_bucket = (job.location_bucket or "").lower().strip()

    if pref_modes:
        # Candidate strictly wants remote only
        if pref_modes == {"remote"}:
            if job_bucket in {"onsite", "in_office"}:
                reasons.append("Candidate strictly requires remote work; job is explicitly on-site")
        # Candidate requires on-site only
        elif pref_modes == {"onsite"}:
            if job_bucket == "remote":
                reasons.append("Candidate strictly requires on-site work; job is remote")

    # Location city/country match (only applied if job location is known and job is not remote)
    if preferences.locations and job_bucket != "remote":
        if job.location:
            job_loc_lower = job.location.lower()
            matched_loc = any(loc.lower().strip() in job_loc_lower for loc in preferences.locations if loc.strip())
            if not matched_loc:
                reasons.append(
                    f"Job location '{job.location}' does not match any preferred locations: {preferences.locations}"
                )
        else:
            missing_fields.append("location")

    # 8. Employment Type Filter
    pref_types = {t.lower().strip() for t in preferences.employment_types if t.strip()}
    if pref_types:
        if job.employment_type:
            job_emp = job.employment_type.lower().strip()
            # If candidate wants full-time only, and job is internship or contract
            matched_type = any(t in job_emp for t in pref_types)
            if not matched_type:
                reasons.append(
                    f"Job employment type '{job.employment_type}' does not match preferred types: {preferences.employment_types}"
                )
        else:
            missing_fields.append("employment_type")

    # 9. Experience / Seniority Ceiling Filter
    # If candidate is a junior/fresher with maximum experience ceiling
    if preferences.max_experience_years is not None:
        explicit_req_years = extract_min_experience_years(
            job.experience_requirements or job.description
        )
        if explicit_req_years is not None:
            if explicit_req_years > preferences.max_experience_years:
                reasons.append(
                    f"Job requires {explicit_req_years:.1f}+ years experience, exceeding candidate ceiling of {preferences.max_experience_years:.1f} years"
                )
        else:
            # Check title for senior/staff keywords if candidate is junior/intern
            pref_levels = {lvl.lower().strip() for lvl in preferences.levels}
            if pref_levels and pref_levels.issubset({"intern", "junior", "fresher"}):
                if SENIORITY_KEYWORDS_REGEX.search(job.title):
                    reasons.append(
                        f"Job title '{job.title}' implies senior role, incompatible with junior/intern preference"
                    )
            missing_fields.append("experience_requirements")

    # 10. Salary Requirement Filter
    if preferences.min_salary is not None:
        if job.salary and job.salary.max_amount is not None:
            # Compare if currency matches or not specified
            curr_match = (
                not preferences.currency
                or not job.salary.currency
                or preferences.currency.upper() == job.salary.currency.upper()
            )
            if curr_match and job.salary.max_amount < preferences.min_salary:
                reasons.append(
                    f"Job maximum salary ({job.salary.max_amount:,.2f}) is below minimum requirement ({preferences.min_salary:,.2f})"
                )
        else:
            missing_fields.append("salary")

    return HardFilterResult(
        passed=len(reasons) == 0,
        reasons=reasons,
        missing_fields=missing_fields,
    )
