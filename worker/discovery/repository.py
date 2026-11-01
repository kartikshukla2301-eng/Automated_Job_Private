"""Job Repository abstraction and in-memory implementation for deterministic testing.

Following Section 10 and Section 14 (jobs table schema):
- Enforces unique constraint: (platform, external_id)
- Manages canonical_key indexing
- Detects content hash changes for updated listings
- Thread-safe in-memory implementation
- Interface designed for clean future PostgreSQL integration
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple, runtime_checkable
from uuid import UUID

from worker.discovery.models import Job, JobStatus


@runtime_checkable
class JobRepository(Protocol):
    """Protocol defining the repository contract for normalized Job persistence."""

    async def save(self, job: Job) -> Job:
        """Insert or update a Job record.

        Enforces (platform, external_id) uniqueness. If listing exists:
        - If content_hash has changed, updates description, hash, and updated_at.
        - Preserves original id, first_seen_at, and created_at.
        """
        ...

    async def get_by_id(self, job_id: UUID) -> Optional[Job]:
        """Retrieve job by primary key UUID."""
        ...

    async def get_by_platform_and_external_id(
        self, platform: str, external_id: str
    ) -> Optional[Job]:
        """Retrieve job by unique constraint (platform, external_id)."""
        ...

    async def get_by_canonical_key(self, canonical_key: str) -> List[Job]:
        """Retrieve all jobs matching a canonical deduplication key."""
        ...

    async def list_jobs(
        self,
        platform: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Job]:
        """List jobs with optional platform and status filtering."""
        ...

    async def count(
        self,
        platform: Optional[str] = None,
        status: Optional[JobStatus] = None,
    ) -> int:
        """Count jobs matching optional platform and status filters."""
        ...

    async def update_score(
        self,
        job_id: UUID,
        score: float,
        score_breakdown: Dict[str, Any],
        status: Optional[JobStatus] = None,
    ) -> Optional[Job]:
        """Update job score, score_breakdown, and status in persistence."""
        ...


class InMemoryJobRepository:
    """Deterministic, thread-safe in-memory JobRepository implementation."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._jobs: Dict[UUID, Job] = {}
        self._platform_ext_index: Dict[Tuple[str, str], UUID] = {}
        self._canonical_key_index: Dict[str, Set[UUID]] = defaultdict(set)

    async def save(self, job: Job) -> Job:
        async with self._lock:
            key = (job.platform.lower(), job.external_id)
            now = datetime.now(timezone.utc)

            if key in self._platform_ext_index:
                # Existing job found
                existing_id = self._platform_ext_index[key]
                existing_job = self._jobs[existing_id]

                # If content hash changed, update description and updated_at
                # Preserve immutable fields: id, first_seen_at, created_at
                is_content_changed = existing_job.content_hash != job.content_hash

                updated_job = existing_job.model_copy(
                    update={
                        "title": job.title,
                        "normalized_title": job.normalized_title,
                        "company": job.company,
                        "normalized_company": job.normalized_company,
                        "canonical_key": job.canonical_key,
                        "url": job.url,
                        "description": job.description if is_content_changed else existing_job.description,
                        "description_html": job.description_html if is_content_changed else existing_job.description_html,
                        "content_hash": job.content_hash if is_content_changed else existing_job.content_hash,
                        "location": job.location,
                        "location_bucket": job.location_bucket,
                        "employment_type": job.employment_type or existing_job.employment_type,
                        "experience_requirements": job.experience_requirements or existing_job.experience_requirements,
                        "salary": job.salary or existing_job.salary,
                        "posted_at": job.posted_at or existing_job.posted_at,
                        "metadata": {**existing_job.metadata, **job.metadata},
                        "updated_at": now,
                    }
                )

                # Re-index canonical key if it changed
                if existing_job.canonical_key != updated_job.canonical_key:
                    self._canonical_key_index[existing_job.canonical_key].discard(existing_id)
                    self._canonical_key_index[updated_job.canonical_key].add(existing_id)

                self._jobs[existing_id] = updated_job
                return updated_job

            # New job insertion
            self._jobs[job.id] = job
            self._platform_ext_index[key] = job.id
            self._canonical_key_index[job.canonical_key].add(job.id)
            return job

    async def get_by_id(self, job_id: UUID) -> Optional[Job]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def get_by_platform_and_external_id(
        self, platform: str, external_id: str
    ) -> Optional[Job]:
        async with self._lock:
            key = (platform.lower(), external_id)
            job_id = self._platform_ext_index.get(key)
            if job_id:
                return self._jobs.get(job_id)
            return None

    async def get_by_canonical_key(self, canonical_key: str) -> List[Job]:
        async with self._lock:
            job_ids = self._canonical_key_index.get(canonical_key, set())
            return [self._jobs[jid] for jid in job_ids if jid in self._jobs]

    async def list_jobs(
        self,
        platform: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Job]:
        async with self._lock:
            results = list(self._jobs.values())
            if platform:
                p_lower = platform.lower()
                results = [j for j in results if j.platform.lower() == p_lower]
            if status:
                results = [j for j in results if j.status == status]

            # Deterministic sorting by first_seen_at desc, then id
            results.sort(key=lambda j: (j.first_seen_at, str(j.id)), reverse=True)
            return results[offset : offset + limit]

    async def count(
        self,
        platform: Optional[str] = None,
        status: Optional[JobStatus] = None,
    ) -> int:
        async with self._lock:
            count = 0
            for job in self._jobs.values():
                if platform and job.platform.lower() != platform.lower():
                    continue
                if status and job.status != status:
                    continue
                count += 1
            return count

    async def update_score(
        self,
        job_id: UUID,
        score: float,
        score_breakdown: Dict[str, Any],
        status: Optional[JobStatus] = None,
    ) -> Optional[Job]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            update_data: Dict[str, Any] = {
                "score": score,
                "score_breakdown": score_breakdown,
                "updated_at": datetime.now(timezone.utc),
            }
            if status is not None:
                update_data["status"] = status
            updated_job = job.model_copy(update=update_data)
            self._jobs[job_id] = updated_job
            return updated_job
