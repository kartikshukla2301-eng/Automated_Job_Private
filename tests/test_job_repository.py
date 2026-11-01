"""Tests for JobRepository protocol and InMemoryJobRepository implementation."""

from datetime import datetime, timezone
import pytest

from worker.discovery.models import Job, JobStatus
from worker.discovery.normalization import compute_canonical_key, compute_content_hash
from worker.discovery.repository import InMemoryJobRepository


@pytest.fixture
def repo() -> InMemoryJobRepository:
    return InMemoryJobRepository()


def make_job(
    platform: str = "greenhouse",
    external_id: str = "job-1",
    company: str = "Acme",
    title: str = "Backend Engineer",
    description: str = "Build systems.",
) -> Job:
    chash = compute_content_hash(description, fallback_title=title)
    ckey = compute_canonical_key(company, title, "remote")
    return Job(
        platform=platform,
        external_id=external_id,
        canonical_key=ckey,
        company=company,
        normalized_company=company.lower(),
        title=title,
        normalized_title=title.lower(),
        url=f"https://example.com/{platform}/{external_id}",
        description=description,
        location="Remote",
        location_bucket="remote",
        content_hash=chash,
        status=JobStatus.DISCOVERED,
    )


class TestInMemoryJobRepository:
    @pytest.mark.asyncio
    async def test_save_and_retrieve_by_id(self, repo: InMemoryJobRepository):
        job = make_job(external_id="101")
        saved = await repo.save(job)
        assert saved.id == job.id

        retrieved = await repo.get_by_id(saved.id)
        assert retrieved is not None
        assert retrieved.external_id == "101"
        assert retrieved.title == "Backend Engineer"

    @pytest.mark.asyncio
    async def test_retrieve_by_platform_and_external_id(self, repo: InMemoryJobRepository):
        job = make_job(platform="lever", external_id="lev-888")
        await repo.save(job)

        found = await repo.get_by_platform_and_external_id("lever", "lev-888")
        assert found is not None
        assert found.external_id == "lev-888"

        not_found = await repo.get_by_platform_and_external_id("lever", "nonexistent")
        assert not_found is None

    @pytest.mark.asyncio
    async def test_update_job_when_content_changes(self, repo: InMemoryJobRepository):
        job = make_job(external_id="job-1", description="Original description text.")
        saved = await repo.save(job)
        orig_id = saved.id
        orig_created_at = saved.created_at
        orig_first_seen = saved.first_seen_at

        # Save updated description for the same external ID
        updated = make_job(external_id="job-1", description="Updated description with new requirements.")
        saved_updated = await repo.save(updated)

        assert saved_updated.id == orig_id  # Preserves primary key
        assert saved_updated.created_at == orig_created_at  # Preserves created_at
        assert saved_updated.first_seen_at == orig_first_seen  # Preserves first_seen_at
        assert saved_updated.description == "Updated description with new requirements."
        assert saved_updated.content_hash != job.content_hash
        assert saved_updated.updated_at >= saved.updated_at

    @pytest.mark.asyncio
    async def test_duplicate_job_not_duplicated_in_storage(self, repo: InMemoryJobRepository):
        job = make_job(external_id="job-dup")
        await repo.save(job)
        await repo.save(job)

        count = await repo.count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_distinct_jobs_not_merged_incorrectly(self, repo: InMemoryJobRepository):
        # Two distinct jobs with same title but different external IDs
        job1 = make_job(external_id="id-1", title="Staff Engineer")
        job2 = make_job(external_id="id-2", title="Staff Engineer")

        await repo.save(job1)
        await repo.save(job2)

        count = await repo.count()
        assert count == 2

        by_key = await repo.get_by_canonical_key(job1.canonical_key)
        assert len(by_key) == 2

    @pytest.mark.asyncio
    async def test_list_and_count_with_filters(self, repo: InMemoryJobRepository):
        job_gh = make_job(platform="greenhouse", external_id="gh-1")
        job_lev1 = make_job(platform="lever", external_id="lev-1")
        job_lev2 = make_job(platform="lever", external_id="lev-2")

        await repo.save(job_gh)
        await repo.save(job_lev1)
        await repo.save(job_lev2)

        assert await repo.count() == 3
        assert await repo.count(platform="greenhouse") == 1
        assert await repo.count(platform="lever") == 2

        lever_jobs = await repo.list_jobs(platform="lever", limit=10, offset=0)
        assert len(lever_jobs) == 2
        assert all(j.platform == "lever" for j in lever_jobs)
