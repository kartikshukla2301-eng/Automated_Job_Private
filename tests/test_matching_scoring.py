"""Unit tests for deterministic weighted scoring engine and factor calculations.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
import pytest

from worker.discovery.models import Job, JobStatus, SalaryInfo
from worker.matching.models import (
    DEFAULT_SCORING_WEIGHTS,
    CandidateJobPreferences,
)
from worker.matching.scoring import (
    calculate_candidate_years_experience,
    calculate_match_score,
    normalize_skill,
    score_experience_fit,
    score_location_work_mode,
    score_project_evidence,
    score_role_relevance,
    score_skills,
)
from worker.profile.models import (
    CandidateDetails,
    ExperienceEntry,
    ProfileSnapshot,
    ProjectEntry,
    SkillEntry,
)


@pytest.fixture
def mock_snapshot() -> ProfileSnapshot:
    return ProfileSnapshot(
        schema_version=1,
        profile_version="v1.0-test",
        synced_at=datetime.now(timezone.utc),
        candidate=CandidateDetails(
            name="Alice Candidate",
            email="alice@example.com",
            location="Bengaluru, India",
            skills=[
                SkillEntry(name="Python", years=3.0),
                SkillEntry(name="TypeScript", years=2.0),
                SkillEntry(name="React", years=2.0),
                SkillEntry(name="PostgreSQL", years=2.0),
                SkillEntry(name="Docker", years=1.5),
            ],
            experience=[
                ExperienceEntry(
                    company="Alpha Tech",
                    title="Software Engineer",
                    start_date="2023-01",
                    end_date="2025-01",
                    is_current=False,
                    description="Full stack development using Python and React.",
                ),
                ExperienceEntry(
                    company="Beta Labs",
                    title="Junior Developer",
                    start_date="2022-01",
                    end_date="2022-12",
                    is_current=False,
                    description="Backend API services.",
                ),
            ],
            projects=[
                ProjectEntry(
                    title="Cloud Dashboard",
                    description="Real-time metrics platform",
                    technologies=["Python", "FastAPI", "React", "Docker"],
                )
            ],
        ),
    )


@pytest.fixture
def test_job() -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        platform="lever",
        external_id="lev-9988",
        canonical_key="acme_corp:backend_engineer:remote",
        company="Acme Corp",
        normalized_company="acme corp",
        title="Backend Engineer",
        normalized_title="backend engineer",
        url="https://jobs.lever.co/acme/9988",
        description="Looking for a Backend Engineer with Python, Docker, and PostgreSQL experience. 2+ years experience.",
        location="Remote",
        location_bucket="remote",
        employment_type="Full-time",
        experience_requirements="2+ years",
        salary=SalaryInfo(min_amount=80000.0, max_amount=110000.0, currency="USD"),
        posted_at=now,
        first_seen_at=now,
        content_hash="b" * 64,
        status=JobStatus.DISCOVERED,
    )


def test_scoring_weights_align_with_architecture():
    """Verify weights match Section 10 of locked architecture exactly."""
    assert DEFAULT_SCORING_WEIGHTS["required_skills"] == 0.30
    assert DEFAULT_SCORING_WEIGHTS["role_relevance"] == 0.20
    assert DEFAULT_SCORING_WEIGHTS["experience_fit"] == 0.15
    assert DEFAULT_SCORING_WEIGHTS["preferred_skills"] == 0.15
    assert DEFAULT_SCORING_WEIGHTS["location_work_mode"] == 0.10
    assert DEFAULT_SCORING_WEIGHTS["project_evidence"] == 0.10
    assert round(sum(DEFAULT_SCORING_WEIGHTS.values()), 4) == 1.0000


def test_skills_synonym_normalization():
    assert normalize_skill("js") == "javascript"
    assert normalize_skill("TS") == "typescript"
    assert normalize_skill("py") == "python"
    assert normalize_skill("golang") == "go"
    assert normalize_skill("k8s") == "kubernetes"
    assert normalize_skill("postgres") == "postgresql"


def test_skills_scoring_perfect_and_partial():
    candidate_skills = {"python", "typescript", "react"}

    # Perfect match
    score, matched, missing = score_skills(["Python", "React"], candidate_skills, "")
    assert score == 100.0
    assert set(matched) == {"Python", "React"}
    assert len(missing) == 0

    # Partial match
    score, matched, missing = score_skills(["Python", "Go", "Rust", "React"], candidate_skills, "")
    assert score == 50.0
    assert set(matched) == {"Python", "React"}
    assert set(missing) == {"Go", "Rust"}


def test_role_relevance_scoring():
    # Exact match
    assert score_role_relevance(["Backend Engineer"], "Backend Engineer") == 100.0
    # Substring match
    assert score_role_relevance(["Backend Engineer"], "Senior Backend Engineer, Platform") >= 85.0
    # Partial token match
    assert score_role_relevance(["Software Engineer"], "Backend Developer") >= 30.0


def test_experience_fit_scoring(test_job):
    # Candidate with 3 years meets 2+ years requirement
    score, req_years = score_experience_fit(3.0, test_job)
    assert score == 100.0
    assert req_years == 2.0

    # Candidate with 0.5 years vs 5+ years requirement
    senior_job = test_job.model_copy(update={"experience_requirements": "5+ years"})
    score, req_years = score_experience_fit(0.5, senior_job)
    assert score < 60.0
    assert req_years == 5.0


def test_calculate_candidate_years_experience(mock_snapshot):
    years = calculate_candidate_years_experience(mock_snapshot)
    assert years >= 2.0  # 2023-2025 is ~2-3 years


def test_location_work_mode_scoring(test_job):
    prefs_remote = CandidateJobPreferences(work_modes=["remote"])
    assert score_location_work_mode(prefs_remote, test_job) == 100.0


def test_project_evidence_scoring(mock_snapshot):
    # Mock project contains Python, FastAPI, React, Docker
    job_text = "we build apis using python and fastapi with docker containers"
    score = score_project_evidence(mock_snapshot, job_text)
    assert score >= 85.0


def test_calculate_match_score_full_pipeline(test_job, mock_snapshot):
    prefs = CandidateJobPreferences(
        roles=["Backend Engineer"],
        required_skills=["Python", "PostgreSQL"],
        preferred_skills=["Docker", "Kubernetes"],
        work_modes=["remote"],
        locations=["Bengaluru"],
    )

    breakdown, explanation = calculate_match_score(test_job, mock_snapshot, prefs)

    assert breakdown.raw_score >= 70.0
    assert breakdown.final_score == breakdown.raw_score
    assert breakdown.required_skills_score == 100.0
    assert breakdown.role_relevance_score == 100.0
    assert len(explanation.positive_contributions) > 0
    assert "Overall" in explanation.summary
    assert "Skills" in explanation.summary
