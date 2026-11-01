"""Integration tests for JobMatchingService, borderline LLM review, and deduplication safety.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10, Section 15)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import httpx
import pytest

from services.api.config import LLMConfig
from worker.core.llm_gateway import (
    InMemoryLLMCache,
    InMemoryLLMCallLedger,
    LLMGateway,
    OpenRouterClient,
)
from worker.discovery.models import Job, JobStatus, SalaryInfo
from worker.discovery.repository import InMemoryJobRepository
from worker.matching.deduplication import (
    DuplicateClassification,
    classify_duplicate_relationship,
)
from worker.matching.embedding import DeterministicFallbackEmbeddingProvider
from worker.matching.models import (
    CandidateJobPreferences,
    JobMatchRequest,
    MatchDecision,
)
from worker.matching.service import JobMatchingService
from worker.profile.models import (
    CandidateDetails,
    ExperienceEntry,
    ProfileSnapshot,
    ProjectEntry,
    SkillEntry,
)


@pytest.fixture
def test_profile() -> ProfileSnapshot:
    return ProfileSnapshot(
        schema_version=1,
        profile_version="v1.0-match",
        synced_at=datetime.now(timezone.utc),
        candidate=CandidateDetails(
            name="Bob Developer",
            email="bob@example.com",
            location="Bengaluru, India",
            skills=[
                SkillEntry(name="Python", years=3.0),
                SkillEntry(name="FastAPI", years=2.0),
                SkillEntry(name="PostgreSQL", years=2.0),
                SkillEntry(name="Docker", years=1.0),
            ],
            experience=[
                ExperienceEntry(
                    company="Cloud Innovators",
                    title="Backend Developer",
                    start_date="2022-06",
                    end_date="2024-12",
                    is_current=False,
                    description="Designed backend microservices in Python.",
                )
            ],
            projects=[
                ProjectEntry(
                    title="API Engine",
                    description="High-throughput API gateway",
                    technologies=["Python", "FastAPI", "Docker"],
                )
            ],
        ),
    )


@pytest.fixture
def matching_preferences() -> CandidateJobPreferences:
    return CandidateJobPreferences(
        roles=["Backend Developer", "Software Engineer"],
        required_skills=["Python", "FastAPI"],
        preferred_skills=["PostgreSQL", "Docker"],
        locations=["Bengaluru"],
        work_modes=["remote", "hybrid"],
        levels=["junior", "mid"],
        employment_types=["full-time"],
        max_job_age_hours=24,
    )


def create_job(
    external_id: str,
    title: str = "Backend Developer",
    company: str = "Fintech Labs",
    description: str = "We need a Backend Developer with Python and FastAPI skills.",
    location_bucket: str = "remote",
    status: JobStatus = JobStatus.DISCOVERED,
) -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        platform="greenhouse",
        external_id=external_id,
        canonical_key=f"fintech_labs:{title.lower().replace(' ', '_')}:{location_bucket}",
        company=company,
        normalized_company="fintech labs",
        title=title,
        normalized_title=title.lower(),
        url=f"https://boards.greenhouse.io/fintech/{external_id}",
        description=description,
        location="Remote",
        location_bucket=location_bucket,
        employment_type="Full-time",
        posted_at=now - timedelta(hours=1),
        first_seen_at=now - timedelta(hours=1),
        content_hash="c" * 64,
        status=status,
    )


@pytest.mark.asyncio
async def test_match_job_clean_match_flow(test_profile, matching_preferences):
    repo = InMemoryJobRepository()
    job = create_job("gh-101")
    await repo.save(job)

    service = JobMatchingService(
        repository=repo,
        embedding_provider=DeterministicFallbackEmbeddingProvider(),
        threshold=65.0,
    )

    req = JobMatchRequest(job=job, profile=test_profile, preferences=matching_preferences)
    result = await service.match_job(req)

    assert result.decision == MatchDecision.MATCH
    assert result.passed_hard_filters is True
    assert result.score >= 65.0
    assert result.breakdown.embedding_similarity is not None

    # Verify repository status and score updated
    updated = await repo.get_by_id(job.id)
    assert updated.score == result.score
    assert updated.status == JobStatus.MATCHED
    assert updated.score_breakdown["raw_score"] == result.score


@pytest.mark.asyncio
async def test_match_job_hard_filter_exclusion(test_profile, matching_preferences):
    repo = InMemoryJobRepository()
    # Onsite job when candidate strictly requires remote
    prefs = matching_preferences.model_copy(update={"work_modes": ["remote"]})
    onsite_job = create_job("gh-102", location_bucket="onsite")
    await repo.save(onsite_job)

    service = JobMatchingService(repository=repo, threshold=65.0)

    req = JobMatchRequest(job=onsite_job, profile=test_profile, preferences=prefs)
    result = await service.match_job(req)

    assert result.decision == MatchDecision.EXCLUDED
    assert result.passed_hard_filters is False
    assert result.score == 0.0

    # Verify repository updated to REJECTED
    updated = await repo.get_by_id(onsite_job.id)
    assert updated.score == 0.0
    assert updated.status == JobStatus.REJECTED


@pytest.mark.asyncio
async def test_borderline_llm_review_accepts_job(test_profile):
    # Candidate with partial skills resulting in borderline score ~58-65
    prefs = CandidateJobPreferences(
        roles=["Backend Developer"],
        required_skills=["Python", "Go", "Rust"],  # Candidate only has Python
        preferred_skills=["PostgreSQL"],
        work_modes=["remote"],
    )
    job = create_job(
        "gh-borderline-1",
        description="We need a Backend Developer with Python, Go, and Rust skills.",
    )

    # Mock OpenRouter returning MATCH
    mock_payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "decision": "MATCH",
                            "confidence": 0.85,
                            "score_adjustment": 8.0,
                            "reason": "Strong Python and FastAPI project experience compensates for missing Go.",
                        }
                    ),
                }
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }

    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=mock_payload))
    async with httpx.AsyncClient(transport=transport) as mock_http:
        client = OpenRouterClient(api_key="test-key", http_client=mock_http)
        gateway = LLMGateway(client=client, config=LLMConfig(), ledger=InMemoryLLMCallLedger(), cache=InMemoryLLMCache())

        service = JobMatchingService(
            llm_gateway=gateway,
            threshold=65.0,
            borderline_band=(50.0, 80.0),
        )

        req = JobMatchRequest(job=job, profile=test_profile, preferences=prefs, allow_borderline_llm=True)
        result = await service.match_job(req)

        assert result.breakdown.llm_review_applied is True
        assert result.breakdown.llm_adjustment == 8.0
        assert result.decision == MatchDecision.MATCH
        assert any("Borderline LLM Review: Strong Python" in p for p in result.explanation.positive_contributions)


@pytest.mark.asyncio
async def test_borderline_llm_handles_malformed_response_gracefully(test_profile):
    prefs = CandidateJobPreferences(
        roles=["Backend Developer"],
        required_skills=["Python", "Go"],
        work_modes=["remote"],
    )
    job = create_job(
        "gh-borderline-2",
        description="We need a Backend Developer with Python, Go, and Rust skills.",
    )

    # Mock OpenRouter returning malformed non-JSON text
    mock_payload = {
        "choices": [{"message": {"role": "assistant", "content": "I cannot decide right now."}}],
        "usage": {"total_tokens": 10},
    }

    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=mock_payload))
    async with httpx.AsyncClient(transport=transport) as mock_http:
        client = OpenRouterClient(api_key="test-key", http_client=mock_http)
        gateway = LLMGateway(client=client, config=LLMConfig(), ledger=InMemoryLLMCallLedger(), cache=InMemoryLLMCache())

        service = JobMatchingService(
            llm_gateway=gateway,
            threshold=65.0,
            borderline_band=(40.0, 75.0),
        )

        req = JobMatchRequest(job=job, profile=test_profile, preferences=prefs, allow_borderline_llm=True)
        result = await service.match_job(req)

        # Fails safe: LLM review not applied, retains deterministic score
        assert result.breakdown.llm_review_applied is False
        assert result.score == result.breakdown.raw_score


@pytest.mark.asyncio
async def test_hard_filters_never_overridden_by_llm(test_profile, matching_preferences):
    # Company is blocklisted
    prefs = matching_preferences.model_copy(update={"blocklisted_companies": ["Fintech Labs"]})
    job = create_job("gh-blocked")

    # Even if LLM would enthusiastically match, LLM is NEVER called because hard filter excludes it
    transport = httpx.MockTransport(lambda r: pytest.fail("LLM must not be called for hard-filtered jobs!"))
    async with httpx.AsyncClient(transport=transport) as mock_http:
        client = OpenRouterClient(api_key="test-key", http_client=mock_http)
        gateway = LLMGateway(client=client, config=LLMConfig(), ledger=InMemoryLLMCallLedger(), cache=InMemoryLLMCache())

        service = JobMatchingService(llm_gateway=gateway, threshold=65.0)
        req = JobMatchRequest(job=job, profile=test_profile, preferences=prefs, allow_borderline_llm=True)

        result = await service.match_job(req)
        assert result.decision == MatchDecision.EXCLUDED
        assert result.passed_hard_filters is False


@pytest.mark.asyncio
async def test_batch_matching_stable_deterministic_ranking(test_profile, matching_preferences):
    job1 = create_job("gh-batch-1", title="Backend Developer")  # High score
    job2 = create_job("gh-batch-2", title="Unrelated Nurse", description="Medical nursing")  # Low score
    job3 = create_job("gh-batch-3", title="Software Engineer")  # High score

    service = JobMatchingService(threshold=65.0)
    requests = [
        JobMatchRequest(job=job2, profile=test_profile, preferences=matching_preferences),
        JobMatchRequest(job=job1, profile=test_profile, preferences=matching_preferences),
        JobMatchRequest(job=job3, profile=test_profile, preferences=matching_preferences),
    ]

    results = await service.match_jobs_batch(requests)
    assert len(results) == 3

    # Ranking must put MATCH before REJECT, and higher scores first
    assert results[0].decision == MatchDecision.MATCH
    assert results[1].decision == MatchDecision.MATCH
    assert results[2].decision == MatchDecision.REJECT
    assert results[0].score >= results[1].score


@pytest.mark.asyncio
async def test_deduplication_safety_classification():
    job_a = create_job("ext-1")
    job_b = create_job("ext-1")
    # 1. Exact platform + external ID
    assert await classify_duplicate_relationship(job_a, job_b) == DuplicateClassification.IDENTICAL_EXTERNAL_ID

    # 2. Cross-platform exact (same canonical key and same content_hash)
    job_c = job_a.model_copy(update={"platform": "lever", "external_id": "lev-202"})
    assert await classify_duplicate_relationship(job_a, job_c) == DuplicateClassification.CROSS_PLATFORM_EXACT

    # 3. Possible duplicate (same canonical key, but different content hash / descriptions)
    # Architecture rule: Preserve both distinct openings!
    job_d = job_a.model_copy(
        update={
            "platform": "lever",
            "external_id": "lev-303",
            "content_hash": "d" * 64,
            "description": "Completely different team requisition.",
        }
    )
    assert await classify_duplicate_relationship(job_a, job_d) == DuplicateClassification.POSSIBLE_DUPLICATE

    # 4. Distinct opening (different canonical key)
    job_e = job_a.model_copy(
        update={
            "canonical_key": "acme:frontend_developer:remote",
            "title": "Frontend Developer",
            "external_id": "lev-404",
        }
    )
    assert await classify_duplicate_relationship(job_a, job_e) == DuplicateClassification.DISTINCT_OPENING
