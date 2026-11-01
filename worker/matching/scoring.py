"""Explainable deterministic weighted scoring engine.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10)
- docs/BUILD_RULES.md
- config/config.yaml

SCORING WEIGHTS (Section 10):
- Required skills: 30% (0.30)
- Role relevance: 20% (0.20)
- Experience fit: 15% (0.15)
- Preferred skills: 15% (0.15)
- Location / work mode: 10% (0.10)
- Project evidence: 10% (0.10)
Total = 100%
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Dict, List, Optional, Set, Tuple

from worker.discovery.models import Job
from worker.matching.hard_filters import extract_min_experience_years
from worker.matching.models import (
    DEFAULT_SCORING_WEIGHTS,
    CandidateJobPreferences,
    MatchExplanation,
    MatchScoreBreakdown,
)
from worker.profile.models import ProfileSnapshot

# Technical skill synonym mappings
SKILL_SYNONYMS: Dict[str, str] = {
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "golang": "go",
    "go": "go",
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    "next": "next.js",
    "nextjs": "next.js",
    "next.js": "next.js",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "aws": "aws",
    "amazon web services": "aws",
    "gcp": "gcp",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "node": "node.js",
    "nodejs": "node.js",
    "node.js": "node.js",
    "fastapi": "fastapi",
    "docker": "docker",
    "playwright": "playwright",
    "selenium": "selenium",
}


def normalize_skill(skill: str) -> str:
    """Normalize skill name with synonym canonicalization."""
    cleaned = skill.lower().strip()
    return SKILL_SYNONYMS.get(cleaned, cleaned)


def calculate_candidate_years_experience(snapshot: ProfileSnapshot) -> float:
    """Calculate total years of experience from profile employment history."""
    now = datetime.now(timezone.utc)
    total_months = 0

    for exp in snapshot.candidate.experience:
        start_year = None
        end_year = None

        if exp.start_date:
            match = re.match(r"^(\d{4})", exp.start_date.strip())
            if match:
                start_year = int(match.group(1))

        if exp.is_current or not exp.end_date:
            end_year = now.year
        elif exp.end_date:
            match = re.match(r"^(\d{4})", exp.end_date.strip())
            if match:
                end_year = int(match.group(1))

        if start_year and end_year and end_year >= start_year:
            # Approximate years to months
            total_months += (end_year - start_year + 1) * 12

    if total_months > 0:
        return round(total_months / 12.0, 1)

    # Fallback to max skill years if experience entries lack dates
    skill_years = [s.years for s in snapshot.candidate.skills if s.years is not None]
    if skill_years:
        return max(skill_years)

    return 0.0


def score_skills(
    target_skills: List[str],
    candidate_skills: Set[str],
    job_text: str,
) -> Tuple[float, List[str], List[str]]:
    """Score skill alignment returning (score, matched_skills, missing_skills)."""
    # If job_text is provided, check candidate and target skill presence in job text
    if job_text:
        candidate_matched_in_job = [
            s for s in candidate_skills if re.search(r"\b" + re.escape(s) + r"\b", job_text)
        ]

        if not target_skills:
            if not candidate_matched_in_job:
                return 0.0, [], []
            ratio = min(1.0, len(candidate_matched_in_job) / max(3, len(candidate_skills) // 2))
            return round(ratio * 100.0, 2), candidate_matched_in_job, []

        target_in_job = [
            s for s in target_skills if re.search(r"\b" + re.escape(normalize_skill(s)) + r"\b", job_text)
        ]

        if not target_in_job and not candidate_matched_in_job:
            # Job text contains none of candidate's target or verified skills
            return 0.0, [], list(target_skills)

        eval_skills = target_in_job if target_in_job else target_skills
    else:
        eval_skills = target_skills

    matched = []
    missing = []
    for skill in eval_skills:
        norm_s = normalize_skill(skill)
        if norm_s in candidate_skills or any(norm_s in cs for cs in candidate_skills):
            matched.append(skill)
        else:
            missing.append(skill)

    score = (len(matched) / len(eval_skills)) * 100.0 if eval_skills else 70.0
    return round(score, 2), matched, missing


ROLE_TOKEN_SYNONYMS = {
    "developer": "engineer",
    "coder": "engineer",
    "programmer": "engineer",
}


def score_role_relevance(target_roles: List[str], job_title: str) -> float:
    """Score title relevance against candidate target roles (0.0 to 100.0)."""
    if not target_roles:
        return 75.0  # Neutral baseline when candidate has open role preferences

    clean_title = job_title.lower().strip()
    best_score = 0.0

    for role in target_roles:
        clean_role = role.lower().strip()
        if clean_role == clean_title:
            return 100.0
        if clean_role in clean_title or clean_title in clean_role:
            best_score = max(best_score, 90.0)
            continue

        # Token intersection with role synonyms
        stopwords = {"and", "or", "the", "in", "for", "of", "to", "at", "a"}
        raw_role_tokens = set(re.findall(r"\w+", clean_role)) - stopwords
        raw_title_tokens = set(re.findall(r"\w+", clean_title)) - stopwords

        role_tokens = {ROLE_TOKEN_SYNONYMS.get(t, t) for t in raw_role_tokens}
        title_tokens = {ROLE_TOKEN_SYNONYMS.get(t, t) for t in raw_title_tokens}

        if role_tokens and title_tokens:
            intersection = role_tokens & title_tokens
            overlap_ratio = len(intersection) / len(role_tokens)
            token_score = overlap_ratio * 80.0
            best_score = max(best_score, token_score)

    return round(min(100.0, best_score), 2)


def score_experience_fit(
    candidate_years: float,
    job: Job,
) -> Tuple[float, Optional[float]]:
    """Score candidate experience fit against job requirements (0.0 to 100.0)."""
    job_req_years = extract_min_experience_years(
        job.experience_requirements or job.description
    )

    if job_req_years is None:
        # Check if job title contains senior keywords
        is_senior = bool(
            re.search(r"\b(senior|lead|staff|principal)\b", job.title, re.IGNORECASE)
        )
        if is_senior:
            score = 100.0 if candidate_years >= 5.0 else max(40.0, candidate_years * 18.0)
        else:
            score = 80.0  # Unspecified mid/junior role
        return round(score, 2), None

    if candidate_years >= job_req_years:
        score = 100.0
    elif candidate_years >= max(0.0, job_req_years - 1.0):
        score = 80.0
    else:
        gap = job_req_years - candidate_years
        score = max(20.0, 100.0 - (gap * 25.0))

    return round(score, 2), job_req_years


def score_location_work_mode(
    preferences: CandidateJobPreferences,
    job: Job,
) -> float:
    """Score location and work mode alignment (0.0 to 100.0)."""
    job_bucket = (job.location_bucket or "").lower().strip()
    pref_modes = {m.lower().strip() for m in preferences.work_modes}

    # Remote job alignment
    if job_bucket == "remote" or (job.location and "remote" in job.location.lower()):
        if not pref_modes or "remote" in pref_modes:
            return 100.0
        return 80.0

    # Specific location match
    if preferences.locations and job.location:
        job_loc_lower = job.location.lower()
        if any(loc.lower() in job_loc_lower for loc in preferences.locations):
            return 100.0
        return 60.0

    # Hybrid or unspecified
    if job_bucket == "hybrid":
        if "hybrid" in pref_modes or not pref_modes:
            return 90.0
        return 70.0

    return 75.0  # Flexible/neutral


def score_project_evidence(
    snapshot: ProfileSnapshot,
    job_text: str,
) -> float:
    """Score candidate project portfolio evidence matching job technologies (0.0 to 100.0)."""
    projects = snapshot.candidate.projects
    if not projects:
        return 0.0

    matched_technologies: Set[str] = set()
    for proj in projects:
        for tech in proj.technologies:
            if re.search(r"\b" + re.escape(tech.lower()) + r"\b", job_text):
                matched_technologies.add(tech.lower())

    tech_count = len(matched_technologies)
    if tech_count >= 3:
        return 100.0
    if tech_count == 2:
        return 85.0
    if tech_count == 1:
        return 70.0
    return 0.0


def calculate_match_score(
    job: Job,
    snapshot: ProfileSnapshot,
    preferences: CandidateJobPreferences,
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[MatchScoreBreakdown, MatchExplanation]:
    """Calculate explainable deterministic weighted score and diagnostic explanation."""
    active_weights = weights or dict(DEFAULT_SCORING_WEIGHTS)
    candidate_skills = {normalize_skill(s.name) for s in snapshot.candidate.skills}
    job_text = f"{job.title} {job.description or ''}".lower()

    # 1. Required Skills Score (30%)
    req_score, req_matched, req_missing = score_skills(
        preferences.required_skills,
        candidate_skills,
        job_text,
    )

    # 2. Preferred Skills Score (15%)
    pref_score, pref_matched, _ = score_skills(
        preferences.preferred_skills,
        candidate_skills,
        job_text,
    )

    # 3. Role Relevance Score (20%)
    role_score = score_role_relevance(preferences.roles, job.title)

    # 4. Experience Fit Score (15%)
    cand_years = calculate_candidate_years_experience(snapshot)
    exp_score, job_req_years = score_experience_fit(cand_years, job)

    # 5. Location / Work Mode Score (10%)
    loc_score = score_location_work_mode(preferences, job)

    # 6. Project Evidence Score (10%)
    proj_score = score_project_evidence(snapshot, job_text)

    # Weighted sum calculation
    raw_score = (
        req_score * active_weights.get("required_skills", 0.30)
        + role_score * active_weights.get("role_relevance", 0.20)
        + exp_score * active_weights.get("experience_fit", 0.15)
        + pref_score * active_weights.get("preferred_skills", 0.15)
        + loc_score * active_weights.get("location_work_mode", 0.10)
        + proj_score * active_weights.get("project_evidence", 0.10)
    )
    raw_score = round(max(0.0, min(100.0, raw_score)), 2)

    # Contributions and Explanations
    positive: List[str] = []
    negative: List[str] = []
    missing_info: List[str] = []

    if req_score >= 75.0:
        positive.append(f"Strong required skills alignment ({req_score:.0f}%, matched: {', '.join(req_matched[:4]) or 'none'})")
    elif req_score < 60.0:
        negative.append(f"Low required skills alignment ({req_score:.0f}%)")

    if req_missing:
        missing_info.append(f"Missing required skills: {', '.join(req_missing)}")

    if role_score >= 80.0:
        positive.append(f"High role title relevance ({role_score:.0f}%)")
    elif role_score < 60.0:
        negative.append(f"Weak role title match ({role_score:.0f}%)")

    if exp_score >= 80.0:
        positive.append(f"Candidate experience ({cand_years:.1f}y) fits job requirements")
    elif exp_score < 60.0:
        negative.append(
            f"Experience gap: candidate has {cand_years:.1f}y vs required {job_req_years or 'senior'}y"
        )

    if loc_score >= 90.0:
        positive.append("Work mode and location strongly align with preferences")
    elif loc_score < 70.0:
        negative.append("Location or work mode is not optimal for candidate")

    if proj_score >= 80.0:
        positive.append("Candidate project portfolio demonstrates matching technologies")

    if not job.salary:
        missing_info.append("Salary information not disclosed")
    if not job.experience_requirements:
        missing_info.append("Explicit experience requirements not stated")

    summary_str = (
        f"Overall {raw_score:.1f} | "
        f"Skills {req_score:.0f} | "
        f"Role {role_score:.0f} | "
        f"Experience {exp_score:.0f} | "
        f"Location {loc_score:.0f}"
    )
    if req_missing:
        summary_str += f" | Missing: {', '.join(req_missing[:3])}"

    breakdown = MatchScoreBreakdown(
        required_skills_score=req_score,
        role_relevance_score=role_score,
        experience_fit_score=exp_score,
        preferred_skills_score=pref_score,
        location_work_mode_score=loc_score,
        project_evidence_score=proj_score,
        weights=active_weights,
        raw_score=raw_score,
        embedding_similarity=None,
        llm_review_applied=False,
        llm_adjustment=None,
        final_score=raw_score,
    )

    explanation = MatchExplanation(
        positive_contributions=positive,
        negative_contributions=negative,
        missing_information=missing_info,
        summary=summary_str,
    )

    return breakdown, explanation
