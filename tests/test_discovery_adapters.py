"""Tests for Greenhouse and Lever discovery adapters."""

import json
from pathlib import Path
import httpx
import pytest

from worker.discovery.models import JobStatus
from worker.providers.exceptions import (
    ProviderDataError,
    ProviderNetworkError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    UnsafeUrlError,
)
from worker.providers.greenhouse_discovery import GreenhouseDiscoveryAdapter
from worker.providers.lever_discovery import LeverDiscoveryAdapter


@pytest.fixture
def greenhouse_json_fixture() -> dict:
    path = Path("fixtures/discovery/greenhouse_jobs.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def lever_json_fixture() -> list:
    path = Path("fixtures/discovery/lever_postings.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestGreenhouseDiscoveryAdapter:
    @pytest.mark.asyncio
    async def test_fetch_jobs_happy_path(self, greenhouse_json_fixture: dict):
        adapter = GreenhouseDiscoveryAdapter()

        def mock_handler(request: httpx.Request) -> httpx.Response:
            assert "boards-api.greenhouse.io" in str(request.url)
            assert "/v1/boards/acme/jobs" in str(request.url)
            return httpx.Response(200, json=greenhouse_json_fixture)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            jobs = await adapter.fetch_jobs("acme", client=client, company_name="Acme Corp")

        assert len(jobs) == 2

        # Job 1
        job1 = jobs[0]
        assert job1.platform == "greenhouse"
        assert job1.external_id == "1001"
        assert job1.title == "Senior Backend Engineer"
        assert job1.company == "Acme Corp"
        assert job1.normalized_company == "acme"
        assert job1.location_bucket == "remote"
        assert job1.canonical_key == "acme:senior backend engineer:remote"
        assert job1.url == "https://boards.greenhouse.io/acme/jobs/1001"
        assert job1.employment_type == "Full-Time"
        assert job1.salary is not None
        assert job1.salary.min_amount == 160000.0
        assert "malicious script" not in (job1.description or "")
        assert job1.status == JobStatus.DISCOVERED
        assert len(job1.content_hash) == 64

        # Job 2
        job2 = jobs[1]
        assert job2.external_id == "1002"
        assert job2.title == "Frontend Engineer"
        assert job2.employment_type == "Contract"
        assert job2.salary is None  # Never invent missing salary
        assert job2.location_bucket == "onsite"

    @pytest.mark.asyncio
    async def test_skips_malformed_records(self):
        adapter = GreenhouseDiscoveryAdapter()
        payload = {
            "jobs": [
                {"id": None, "title": "Missing ID"},  # Invalid
                {"id": "123", "title": ""},  # Empty title
                {"id": "456", "title": "Valid Engineer"},  # Valid
            ]
        }

        transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
        async with httpx.AsyncClient(transport=transport) as client:
            jobs = await adapter.fetch_jobs("testco", client=client)

        assert len(jobs) == 1
        assert jobs[0].external_id == "456"

    @pytest.mark.asyncio
    async def test_handles_404_not_found(self):
        adapter = GreenhouseDiscoveryAdapter()
        transport = httpx.MockTransport(lambda req: httpx.Response(404, text="Not Found"))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderNotFoundError) as exc_info:
                await adapter.fetch_jobs("nonexistent_company", client=client)
            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_handles_429_rate_limit(self):
        adapter = GreenhouseDiscoveryAdapter()
        transport = httpx.MockTransport(lambda req: httpx.Response(429, text="Too Many Requests"))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderRateLimitError) as exc_info:
                await adapter.fetch_jobs("busyco", client=client)
            assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_handles_500_service_error(self):
        adapter = GreenhouseDiscoveryAdapter()
        transport = httpx.MockTransport(lambda req: httpx.Response(500, text="Internal Server Error"))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderNetworkError):
                await adapter.fetch_jobs("errorco", client=client)

    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        adapter = GreenhouseDiscoveryAdapter()

        def timeout_handler(req: httpx.Request):
            raise httpx.TimeoutException("Connection timed out")

        transport = httpx.MockTransport(timeout_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderTimeoutError):
                await adapter.fetch_jobs("slowco", client=client)

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self):
        adapter = GreenhouseDiscoveryAdapter()
        transport = httpx.MockTransport(lambda req: httpx.Response(200, text="<html>Not JSON</html>"))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderDataError):
                await adapter.fetch_jobs("badco", client=client)

    @pytest.mark.asyncio
    async def test_handles_non_list_jobs_field(self):
        adapter = GreenhouseDiscoveryAdapter()
        transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"jobs": "not a list"}))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderDataError):
                await adapter.fetch_jobs("badco", client=client)

    @pytest.mark.asyncio
    async def test_rejects_unsafe_host(self):
        adapter = GreenhouseDiscoveryAdapter(base_host="evil.com")
        with pytest.raises(UnsafeUrlError):
            await adapter.fetch_jobs("acme")


class TestLeverDiscoveryAdapter:
    @pytest.mark.asyncio
    async def test_fetch_jobs_happy_path(self, lever_json_fixture: list):
        adapter = LeverDiscoveryAdapter()

        def mock_handler(request: httpx.Request) -> httpx.Response:
            assert "api.lever.co" in str(request.url)
            assert "/v0/postings/globex" in str(request.url)
            return httpx.Response(200, json=lever_json_fixture)

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            jobs = await adapter.fetch_jobs("globex", client=client, company_name="Globex Corp")

        assert len(jobs) == 2

        # Job 1
        job1 = jobs[0]
        assert job1.platform == "lever"
        assert job1.external_id == "lever-job-001"
        assert job1.title == "Staff Platform Engineer"
        assert job1.company == "Globex Corp"
        assert job1.normalized_company == "globex"
        assert job1.location_bucket == "hybrid"
        assert job1.employment_type == "Full-time"
        assert job1.url == "https://jobs.lever.co/globex/lever-job-001"
        assert job1.salary is not None
        assert job1.salary.min_amount == 3500000.0
        assert job1.salary.max_amount == 5000000.0
        assert job1.salary.currency == "INR"
        assert job1.salary.interval == "year"
        assert "cloud infrastructure" in (job1.description or "").lower()

        # Job 2
        job2 = jobs[1]
        assert job2.external_id == "lever-job-002"
        assert job2.location_bucket == "remote"
        assert job2.salary is None  # Missing salary not fabricated

    @pytest.mark.asyncio
    async def test_lever_pagination(self):
        # Configure small page size to test pagination loop
        adapter = LeverDiscoveryAdapter(page_size=2)

        page1 = [
            {"id": "lev-1", "text": "Engineer 1", "categories": {"location": "Remote"}, "workplaceType": "remote"},
            {"id": "lev-2", "text": "Engineer 2", "categories": {"location": "Remote"}, "workplaceType": "remote"},
        ]
        page2 = [
            {"id": "lev-3", "text": "Engineer 3", "categories": {"location": "Remote"}, "workplaceType": "remote"},
        ]

        def mock_handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            if "skip=0" in url_str:
                return httpx.Response(200, json=page1)
            elif "skip=2" in url_str:
                return httpx.Response(200, json=page2)
            return httpx.Response(200, json=[])

        transport = httpx.MockTransport(mock_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            jobs = await adapter.fetch_jobs("acme", client=client)

        assert len(jobs) == 3
        assert [j.external_id for j in jobs] == ["lev-1", "lev-2", "lev-3"]

    @pytest.mark.asyncio
    async def test_lever_handles_404_not_found(self):
        adapter = LeverDiscoveryAdapter()
        transport = httpx.MockTransport(lambda req: httpx.Response(404, text="Not Found"))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderNotFoundError):
                await adapter.fetch_jobs("unknown_company", client=client)

    @pytest.mark.asyncio
    async def test_lever_handles_429_rate_limit(self):
        adapter = LeverDiscoveryAdapter()
        transport = httpx.MockTransport(lambda req: httpx.Response(429, text="Rate Limited"))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderRateLimitError):
                await adapter.fetch_jobs("throttled", client=client)

    @pytest.mark.asyncio
    async def test_lever_handles_malformed_payload(self):
        adapter = LeverDiscoveryAdapter()
        transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"error": "not a list"}))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ProviderDataError):
                await adapter.fetch_jobs("badco", client=client)
