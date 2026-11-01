"""Central JobDiscoveryService coordinating provider adapters, normalization, and deduplication.

Following Architecture v1.0 LOCKED and Phase 1.1 Requirements:
- Selects provider adapter (Greenhouse, Lever).
- Fetches listings via isolated adapters.
- Normalizes results into canonical Job models.
- Deduplicates results against JobRepository.
- Tracks provider failures, modified content, duplicates, and rejected records.
- Independent of the HTTP layer (usable from worker, scheduler, or CLI).
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from worker.discovery.models import DiscoverySummary, Job, JobStatus
from worker.discovery.repository import InMemoryJobRepository, JobRepository
from worker.providers.base import JobDiscoveryAdapter
from worker.providers.exceptions import ProviderError, UnsupportedProviderError

logger = logging.getLogger("worker.discovery.service")


class JobDiscoveryService:
    """Central service orchestrating multi-platform job discovery, normalization, and deduplication."""

    def __init__(
        self,
        repository: Optional[JobRepository] = None,
        adapters: Optional[Dict[str, JobDiscoveryAdapter]] = None,
    ) -> None:
        self.repository = repository or InMemoryJobRepository()
        self._adapters: Dict[str, JobDiscoveryAdapter] = {}

        # Register default adapters
        if adapters:
            self._adapters = dict(adapters)
        else:
            from worker.providers.greenhouse_discovery import GreenhouseDiscoveryAdapter
            from worker.providers.lever_discovery import LeverDiscoveryAdapter

            gh = GreenhouseDiscoveryAdapter()
            lv = LeverDiscoveryAdapter()
            self._adapters[gh.name] = gh
            self._adapters[lv.name] = lv

    def register_adapter(self, adapter: JobDiscoveryAdapter) -> None:
        """Register or override a provider discovery adapter."""
        self._adapters[adapter.name.lower()] = adapter

    def get_adapter(self, provider: str) -> JobDiscoveryAdapter:
        """Retrieve registered adapter or raise UnsupportedProviderError."""
        clean = provider.strip().lower()
        if clean not in self._adapters:
            raise UnsupportedProviderError(
                f"Provider '{provider}' is not supported for discovery. Supported: {list(self._adapters.keys())}"
            )
        return self._adapters[clean]

    async def discover(
        self,
        provider: str,
        company: str,
        company_name: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
        **kwargs: Any,
    ) -> DiscoverySummary:
        """Run job discovery for a target provider and company/board.

        1. Selects provider adapter.
        2. Fetches listings with explicit error handling.
        3. Normalizes and deduplicates against the job repository.
        4. Detects updated job descriptions via content hashes.
        5. Returns structured summary report.
        """
        clean_provider = provider.strip().lower()
        clean_company = company.strip()

        summary = DiscoverySummary(
            provider=clean_provider,
            company=clean_company,
        )

        try:
            adapter = self.get_adapter(clean_provider)
        except UnsupportedProviderError as exc:
            summary.errors.append(str(exc))
            return summary

        try:
            discovered_jobs = await adapter.fetch_jobs(
                company=clean_company,
                client=client,
                company_name=company_name,
                **kwargs,
            )
        except ProviderError as exc:
            logger.warning("Provider error during discovery for %s/%s: %s", clean_provider, clean_company, exc)
            summary.errors.append(str(exc))
            return summary
        except Exception as exc:
            logger.exception("Unexpected error during discovery for %s/%s", clean_provider, clean_company)
            summary.errors.append(f"Unexpected discovery failure: {exc}")
            return summary

        summary.total_discovered = len(discovered_jobs)

        for job in discovered_jobs:
            existing = await self.repository.get_by_platform_and_external_id(
                platform=job.platform,
                external_id=job.external_id,
            )

            if existing is not None:
                if existing.content_hash != job.content_hash:
                    # Content updated: persist new description and content hash
                    await self.repository.save(job)
                    summary.updated_jobs += 1
                else:
                    # Content unchanged: duplicate/unchanged listing
                    summary.duplicate_jobs += 1
            else:
                # Check for cross-platform duplicate by canonical key (normalized company + title + bucket)
                existing_canonical = await self.repository.get_by_canonical_key(job.canonical_key)
                is_duplicate = False
                for ex in existing_canonical:
                    # If content hash matches across platforms or titles identical with same content
                    if ex.content_hash == job.content_hash:
                        job_to_save = job.model_copy(update={"status": JobStatus.DUPLICATE})
                        await self.repository.save(job_to_save)
                        summary.duplicate_jobs += 1
                        is_duplicate = True
                        break

                if not is_duplicate:
                    await self.repository.save(job)
                    summary.new_jobs += 1

        return summary
