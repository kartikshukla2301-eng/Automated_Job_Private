"""Unit tests for Resume Manager, Safe Resume Tailoring, and Cover Letter Generation (Phase 1.9).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 6, 8, 14)
- docs/BUILD_RULES.md
"""

from pathlib import Path
import pytest

from worker.profile.cover_letter import CoverLetterGenerator
from worker.profile.exceptions import HallucinationDetectedError
from worker.profile.models import (
    CandidateDetails,
    CandidatePreferences,
    EducationEntry,
    ExperienceEntry,
    ProfileSnapshot,
    ProjectEntry,
    SkillEntry,
)
from worker.profile.resume_intelligence import ResumeIntelligenceEngine
from worker.profile.resume_manager import (
    DuplicateResumeError,
    ResumeManager,
    ResumeNotFoundError,
)


@pytest.fixture
def sample_profile() -> ProfileSnapshot:
    return ProfileSnapshot(
        schema_version=1,
        profile_version="v1.0-intelligence-test",
        candidate=CandidateDetails(
            name="Kartik Shukla",
            email="kartik@example.com",
            phone="+919876543210",
            location="Bangalore, India",
            skills=[
                SkillEntry(name="Python", years=6.0),
                SkillEntry(name="Kubernetes", years=4.0),
                SkillEntry(name="PostgreSQL", years=5.0),
            ],
            experience=[
                ExperienceEntry(
                    title="Staff Platform Engineer",
                    company="TechCorp",
                    location="Bangalore",
                    start_date="2021-01",
                    is_current=True,
                    highlights=[
                        "Architected scalable Kubernetes clusters handling 50k RPS.",
                        "Optimized PostgreSQL queries reducing latency by 40%.",
                        "Automated CI/CD pipelines in Python and Docker.",
                    ],
                )
            ],
            projects=[
                ProjectEntry(
                    title="Distributed Task Queue",
                    description="High throughput task worker pool",
                    technologies=["Python", "Redis", "PostgreSQL"],
                )
            ],
        ),
        preferences=CandidatePreferences(
            roles=["Platform Engineer"],
            locations=["Bangalore"],
            work_modes=["remote"],
        ),
    )


def test_resume_manager_lifecycle(tmp_path: Path):
    storage_dir = tmp_path / "resumes"
    mgr = ResumeManager(storage_dir=storage_dir)

    # 1. Create dummy resume files
    r1_file = tmp_path / "resume_backend.pdf"
    r1_file.write_bytes(b"PDF-1.4 Resume Backend Content 12345")

    r2_file = tmp_path / "resume_platform.pdf"
    r2_file.write_bytes(b"PDF-1.4 Resume Platform Content 67890")

    # 2. Register resumes
    m1 = mgr.register_resume(r1_file, role_family="backend", is_default=True)
    m2 = mgr.register_resume(r2_file, role_family="platform", is_default=False)

    assert m1.role_family == "backend"
    assert m1.is_default is True
    assert m2.role_family == "platform"

    # 3. Duplicate rejection by SHA-256
    with pytest.raises(DuplicateResumeError, match="Duplicate resume detected"):
        mgr.register_resume(r1_file, role_family="backend")

    # 4. Resume retrieval and list
    assert len(mgr.list_resumes()) == 2
    fetched = mgr.get_resume(m1.id)
    assert fetched.filename == "resume_backend.pdf"

    # 5. Selecting resume for job title
    selected_platform = mgr.select_resume_for_job("Senior Kubernetes SRE Engineer")
    assert selected_platform is not None
    assert selected_platform.role_family == "platform"

    selected_backend = mgr.select_resume_for_job("Lead Python Backend Developer")
    assert selected_backend is not None
    assert selected_backend.role_family == "backend"

    # Fallback to default
    selected_other = mgr.select_resume_for_job("Mobile App Designer")
    assert selected_other is not None
    assert selected_other.is_default is True


def test_resume_intelligence_tailoring_and_anti_hallucination(sample_profile: ProfileSnapshot):
    engine = ResumeIntelligenceEngine()

    # 1. Vocabulary extraction
    vocab = engine.extract_verified_vocabulary(sample_profile)
    assert "python" in vocab
    assert "kubernetes" in vocab
    assert "techcorp" in vocab

    # 2. Tailor experience highlights
    job_desc = "Seeking a Kubernetes and Cloud engineer to optimize production container infrastructure."
    tailored = engine.tailor_experience_highlights(
        profile=sample_profile,
        job_description=job_desc,
        target_title="Staff Infrastructure Engineer",
    )

    assert tailored.profile_version == "v1.0-intelligence-test"
    assert "TechCorp" in tailored.tailored_highlights

    # Highest scored bullet for Kubernetes should be prioritized to rank 1
    bullets = tailored.tailored_highlights["TechCorp"]
    assert "Kubernetes" in bullets[0]

    # 3. Anti-hallucination verification succeeds on grounded claims
    engine.verify_groundedness("Architected systems in Python and Kubernetes", sample_profile)

    # 4. Anti-hallucination verification fails on unverified claims
    with pytest.raises(HallucinationDetectedError, match="unverified skill 'solidity'"):
        engine.verify_groundedness("Built smart contracts using Solidity and Rust", sample_profile)


def test_cover_letter_generator(sample_profile: ProfileSnapshot):
    generator = CoverLetterGenerator()

    job_desc = (
        "ScaleOps is hiring a Platform Engineer. <script>malicious_breakout();</script>"
        "Requirements: Kubernetes, PostgreSQL, distributed systems."
    )

    draft = generator.generate_draft(
        profile=sample_profile,
        company="ScaleOps Technologies",
        job_title="Staff Platform Engineer",
        job_description=job_desc,
    )

    # 1. Checks human review invariant
    assert draft.needs_review is True

    # 2. Checks grounded content
    assert "ScaleOps Technologies" in draft.company_name
    assert "TechCorp" in draft.full_text
    assert "Python" in draft.full_text
    assert "Kartik Shukla" in draft.full_text

    # 3. Prompt injection sanitized
    assert "malicious_breakout" not in draft.full_text
    assert "<script>" not in draft.full_text

    # 4. Provenance tracking
    assert len(draft.provenance_hash) == 64
