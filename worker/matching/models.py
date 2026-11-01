"""Canonical matching and scoring models.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10)
- docs/BUILD_RULES.md
- migrations/001_initial_schema.sql (jobs table schema and status constraints)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from worker.discovery.models import Job, JobStatus
from worker.profile.models import CandidatePreferences, ProfileSnapshot


class MatchDecision(str, Enum):
    """Categorical match decisions.

    Strictly deterministic-first; aligns with Section 10 of locked architecture.
    """

    MATCH = "MATCH"
    BORDERLINE = "BORDERLINE"
    REJECT = "REJECT"
    EXCLUDED = "EXCLUDED"
    UNRESOLVED = "UNRESOLVED"


# Default weights locked in Architecture v1.0 Section 10:
# Required skills: 30%
# Role relevance: 20%
# Experience fit: 15%
# Preferred skills: 15%
# Location / work mode: 10%
# Project evidence: 10%
DEFAULT_SCORING_WEIGHTS: Dict[str, float] = {
    "required_skills": 0.30,
    "role_relevance": 0.20,
    "experience_fit": 0.15,
    "preferred_skills": 0.15,
    "location_work_mode": 0.10,
    "project_evidence": 0.10,
}


class MatchScoreBreakdown(BaseModel):
    """Transparent component-level breakdown of job matching score."""

    model_config = ConfigDict(extra="forbid")

    required_skills_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Required skills alignment (0-100)")
    role_relevance_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Title/role relevance score (0-100)")
    experience_fit_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Years and seniority alignment (0-100)")
    preferred_skills_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Preferred skills alignment (0-100)")
    location_work_mode_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Location and work mode fit (0-100)")
    project_evidence_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Project portfolio tech evidence (0-100)")
    weights: Dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_SCORING_WEIGHTS), description="Factor weights")
    raw_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Deterministic weighted score before adjustment")
    embedding_similarity: Optional[float] = Field(default=None, description="Optional vector cosine similarity")
    llm_review_applied: bool = Field(default=False, description="Whether borderline LLM review modified the outcome")
    llm_adjustment: Optional[float] = Field(default=None, description="Score adjustment applied by LLM review if any")
    final_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Final normalized overall match score (0-100)")


class MatchExplanation(BaseModel):
    """Explainable human-readable breakdown of positive and negative factors."""

    model_config = ConfigDict(extra="forbid")

    positive_contributions: List[str] = Field(default_factory=list, description="Factors supporting the match")
    negative_contributions: List[str] = Field(default_factory=list, description="Factors detracting from the match")
    missing_information: List[str] = Field(default_factory=list, description="Missing or undisclosed job fields")
    summary: str = Field(..., description="Single-line concise diagnostic explanation")


class CandidateJobPreferences(BaseModel):
    """Unified job search preferences combining candidate profile defaults with search filters."""

    model_config = ConfigDict(extra="forbid")

    roles: List[str] = Field(default_factory=list, description="Target job titles or role categories")
    locations: List[str] = Field(default_factory=list, description="Preferred work locations")
    work_modes: List[str] = Field(default_factory=list, description="Preferred work modes: remote, hybrid, onsite")
    levels: List[str] = Field(default_factory=list, description="Target seniority levels: intern, junior, mid, senior")
    min_salary: Optional[float] = Field(default=None, ge=0.0, description="Minimum acceptable base salary if stated")
    currency: Optional[str] = Field(default=None, description="Salary currency ISO code (e.g. USD, INR)")
    employment_types: List[str] = Field(default_factory=list, description="Target employment types: full-time, contract, internship")
    blocklisted_companies: List[str] = Field(default_factory=list, description="Companies excluded by candidate")
    blocklisted_keywords: List[str] = Field(default_factory=list, description="Disqualifying keywords in title or body")
    max_job_age_hours: int = Field(default=24, ge=1, description="Maximum posting freshness age in hours")
    required_skills: List[str] = Field(default_factory=list, description="Explicit must-have skills for candidate")
    preferred_skills: List[str] = Field(default_factory=list, description="Nice-to-have secondary skills")
    min_experience_years: Optional[float] = Field(default=None, ge=0.0, description="Candidate minimum experience")
    max_experience_years: Optional[float] = Field(default=None, ge=0.0, description="Seniority ceiling for junior/fresher roles")

    @classmethod
    def from_profile(
        cls,
        snapshot: ProfileSnapshot,
        **overrides: Any,
    ) -> CandidateJobPreferences:
        """Create CandidateJobPreferences initialized from a ProfileSnapshot's preferences."""
        prefs = snapshot.preferences
        skills = [s.name for s in snapshot.candidate.skills]
        init_data: Dict[str, Any] = {
            "roles": list(prefs.roles),
            "locations": list(prefs.locations),
            "work_modes": [m.lower() for m in prefs.work_modes],
            "levels": [lvl.lower() for lvl in prefs.levels],
            "required_skills": skills[:5],
            "preferred_skills": skills[5:],
        }
        init_data.update(overrides)
        return cls(**init_data)


class HardFilterResult(BaseModel):
    """Deterministic result of evaluating all hard eligibility constraints."""

    model_config = ConfigDict(extra="forbid")

    passed: bool = Field(..., description="Whether job passed all mandatory eligibility checks")
    reasons: List[str] = Field(default_factory=list, description="Specific exclusion reasons if rejected")
    missing_fields: List[str] = Field(default_factory=list, description="Job fields that were missing or unknown")


class JobMatchRequest(BaseModel):
    """Input request for evaluating candidate-job fit."""

    model_config = ConfigDict(extra="forbid")

    job: Job = Field(..., description="Canonical discovered job listing")
    profile: ProfileSnapshot = Field(..., description="Verified candidate profile snapshot")
    preferences: Optional[CandidateJobPreferences] = Field(default=None, description="Job search preferences")
    applied_company_cooldowns: Dict[str, datetime] = Field(
        default_factory=dict,
        description="Map of normalized company names to timestamp of last application",
    )
    applied_company_counts_today: Dict[str, int] = Field(
        default_factory=dict,
        description="Map of normalized company names to count of applications made today",
    )
    applied_job_ids: Set[str] = Field(
        default_factory=set,
        description="Set of already applied job identifiers (UUID, external_id, or canonical_key)",
    )
    allow_borderline_llm: bool = Field(default=True, description="Whether borderline band can trigger LLM review")


class JobMatchResult(BaseModel):
    """Complete, explainable candidate-job matching evaluation."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID = Field(..., description="Target Job primary UUID")
    platform: str = Field(..., description="Provider platform name")
    external_id: str = Field(..., description="Provider-specific external ID")
    canonical_key: str = Field(..., description="Key 2 deduplication string")
    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Job title")
    decision: MatchDecision = Field(..., description="Final match decision")
    passed_hard_filters: bool = Field(..., description="Whether job satisfied all hard eligibility criteria")
    hard_filter_reasons: List[str] = Field(default_factory=list, description="Hard filter exclusion reasons if any")
    score: float = Field(..., ge=0.0, le=100.0, description="Overall calibrated score (0.00-100.00)")
    breakdown: MatchScoreBreakdown = Field(..., description="Factor-level score components and weights")
    explanation: MatchExplanation = Field(..., description="Explainable rationale and contributions")
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of evaluation",
    )
