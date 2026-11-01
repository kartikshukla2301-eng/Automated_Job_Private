"""Tests for central JobDiscoveryService."""

import json
from pathlib import Path
from typing import List
import httpx
import pytest

from worker.discovery.models import DiscoverySummary, Job, JobStatus
from worker.discovery.normalization import compute_canonical_key, compute_content_hash
from worker.discovery.repository import InMemoryJobRepository
from worker.discovery.service import JobDiscoveryService
from worker.providers.exceptions import ProviderNetworkError
from worker.providers.greenhouse_discovery import GreenhouseDiscoveryAdapter
from worker.providers.lever_discovery import LeverDiscoveryAdapter


@pytest.fixture
def repo() -> InMemoryJobRepository:
    return InMemoryJobRepository()


@pytest.fixture
def greenhouse_json() -> dict:
    with open("fixtures/discovery/greenhouse_jobs.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def lever_json() -> list:
    with open("fixtures/discovery/lever_postings.json", "r", encoding="utf-8") as f:
        return json.load(f)


class TestJobDiscoveryService:
    @pytest.mark.asyncio
    async def test_discover_greenhouse_new_jobs(self, repo: InMemoryJobRepository, greenhouse_json: dict):
        service = JobDiscoveryService(repository=repo)

        transport = httpx.MockTransport(lambda req: httpx.Response(200, json=greenhouse_json))
        async with httpx.AsyncClient(transport=transport) as client:
            summary = await service.discover("greenhouse", "acme", client=client, company_name="Acme Corp")

        assert summary.provider == "greenhouse"
        assert summary.company == "acme"
        assert summary.total_discovered == 2
        assert summary.new_jobs == 2
        assert summary.updated_jobs == 0
        assert summary.duplicate_jobs == 0
        assert len(summary.errors) == 0

        assert await repo.count() == 2

    @pytest.mark.asyncio
    async def test_discover_deduplicates_on_second_run(self, repo: InMemoryJobRepository, greenhouse_json: dict):
        service = JobDiscoveryService(repository=repo)
        transport = httpx.MockTransport(lambda req: httpx.Response(200, json=greenhouse_json))

        async with httpx.AsyncClient(transport=transport) as client:
            summary1 = await service.discover("greenhouse", "acme", client=client)
            assert summary1.new_jobs == 2

            summary2 = await service.discover("greenhouse", "acme", client=client)
            assert summary2.total_discovered == 2
            assert summary2.new_jobs == 0
            assert summary2.duplicate_jobs == 2

        assert await repo.count() == 2

    @pytest.mark.asyncio
    async def test_discover_detects_changed_job_description(self, repo: InMemoryJobRepository, greenhouse_json: dict):
        service = JobDiscoveryService(repository=repo)

        # Run 1
        transport1 = httpx.MockTransport(lambda req: httpx.Response(200, json=greenhouse_json))
        async with httpx.AsyncClient(transport=transport1) as client:
            await service.discover("greenhouse", "acme", client=client)

        # Run 2 with modified job description for job 1001
        modified_json = dict(greenhouse_json)
        modified_json["jobs"] = [dict(j) for j in greenhouse_json["jobs"]]
        modified_json["jobs"][0]["content"] = "<p>Completely rewritten requirements: Rust and Kubernetes.</p>"

        transport2 = httpx.MockTransport(lambda req: httpx.Response(200, json=modified_json))
        async with httpx.AsyncClient(transport=transport2) as client:
            summary = await service.discover("greenhouse", "acme", client=client)

        assert summary.total_discovered == 2
        assert summary.updated_jobs == 1
        assert summary.duplicate_jobs == 1
        assert summary.new_jobs == 0

        # Verify updated description in repo
        updated_job = await repo.get_by_platform_and_external_id("greenhouse", "1001")
        assert updated_job is not None
        assert "Rust and Kubernetes" in (updated_job.description or "")

    @pytest.mark.asyncio
    async def test_discover_lever_jobs(self, repo: InMemoryJobRepository, lever_json: list):
        service = JobDiscoveryService(repository=repo)

        transport = httpx.MockTransport(lambda req: httpx.Response(200, json=lever_json))
        async with httpx.AsyncClient(transport=transport) as client:
            summary = await service.discover("lever", "globex", client=client)

        assert summary.provider == "lever"
        assert summary.total_discovered == 2
        assert summary.new_jobs == 2
        assert await repo.count(platform="lever") == 2

    @pytest.mark.asyncio
    async def test_cross_platform_duplicate_detection(self, repo: InMemoryJobRepository):
        service = JobDiscoveryService(repository=repo)

        # Pre-populate Greenhouse job
        desc = "Architect distributed storage clusters."
        chash = compute_content_hash(desc)
        ckey = compute_canonical_key("Meta", "Storage Engineer", "remote")

        gh_job = Job(
            platform="greenhouse",
            external_id="gh-77",
            canonical_key=ckey,
            company="Meta",
            normalized_company="meta",
            title="Storage Engineer",
            normalized_title="storage engineer",
            url="https://boards.greenhouse.io/meta/jobs/gh-77",
            description=desc,
            location="Remote",
            location_bucket="remote",
            content_hash=chash,
            status=JobStatus.DISCOVERED,
        )
        await repo.save(gh_job)

        # Mock Lever returning exact same job on Lever
        lever_raw = [
            {
                "id": "lev-77",
                "text": "Storage Engineer",
                "hostedUrl": "https://jobs.lever.co/meta/lev-77",
                "description": desc,
                "categories": {"location": "Remote"},
                "workplaceType": "remote",
            }
        ]

        transport = httpx.MockTransport(lambda req: httpx.Response(200, json=lever_raw))
        async with httpx.AsyncClient(transport=transport) as client:
            summary = await service.discover("lever", "meta", client=client, company_name="Meta")

        # Marked as duplicate, not new
        assert summary.total_discovered == 1
        assert summary.duplicate_jobs == 1
        assert summary.new_jobs == 0

        lev_job = await repo.get_by_platform_and_external_id("lever", "lev-77")
        assert lev_job is not None
        assert lev_job.status == JobStatus.DUPLICATE

    @pytest.mark.asyncio
    async def test_provider_failure_recorded_in_summary(self, repo: InMemoryJobRepository):
        service = JobDiscoveryService(repository=repo)

        transport = httpx.MockTransport(lambda req: httpx.Response(500, text="Internal Error"))
        async with httpx.AsyncClient(transport=transport) as client:
            summary = await service.discover("greenhouse", "down_company", client=client)

        assert summary.total_discovered == 0
        assert len(summary.errors) == 1
        assert "service error" in summary.errors[0].lower() or "500" in summary.errors[0]

    @pytest.mark.asyncio
    async def test_unsupported_provider(self, repo: InMemoryJobRepository):
        service = JobDiscoveryService(repository=repo)
        summary = await service.discover("workday", "some_corp")

        assert summary.total_discovered == 0
        assert len(summary.errors) == 1
        assert "not supported" in summary.errors[0].lower()
