"""Supabase-backed implementation of JobRepository (Phase 2.2).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10, Section 14)
- worker/discovery/repository.py (JobRepository Protocol)
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from worker.discovery.models import Job, JobStatus
from worker.persistence.supabase_client import SupabaseClient

logger = logging.getLogger("worker.persistence.job_repository")


class SupabaseJobRepository:
    """Production job repository backed by Supabase PostgREST."""

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client
        self.table = "jobs"

    def _to_db_payload(self, job: Job) -> Dict[str, Any]:
        return {
            "id": str(job.id),
            "platform": job.platform,
            "external_id": job.external_id,
            "canonical_key": job.canonical_key,
            "company": job.company,
            "normalized_company": job.normalized_company,
            "title": job.title,
            "normalized_title": job.normalized_title,
            "url": str(job.url),
            "description": job.description,
            "posted_at": job.posted_at.isoformat() if job.posted_at else None,
            "first_seen_at": job.first_seen_at.isoformat() if job.first_seen_at else None,
            "content_hash": job.content_hash,
            "score": float(job.score) if job.score is not None else None,
            "score_breakdown": job.score_breakdown,
            "status": job.status.value if isinstance(job.status, JobStatus) else str(job.status),
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }

    def _from_db_row(self, row: Dict[str, Any]) -> Job:
        if "normalized_company" not in row and "company" in row:
            row["normalized_company"] = row["company"].lower()
        if "normalized_title" not in row and "title" in row:
            row["normalized_title"] = row["title"].lower()
        return Job.model_validate(row)

    async def save(self, job: Job) -> Job:
        """Insert or update a Job record enforcing (platform, external_id) uniqueness."""
        existing = await self.get_by_platform_and_external_id(job.platform, job.external_id)
        if existing:
            # Update listing if hash changed
            now = datetime.now(timezone.utc)
            update_data = {
                "title": job.title,
                "url": str(job.url),
                "description": job.description,
                "content_hash": job.content_hash,
                "updated_at": now.isoformat(),
            }
            if job.score is not None:
                update_data["score"] = float(job.score)
                update_data["score_breakdown"] = job.score_breakdown
            if job.status:
                update_data["status"] = job.status.value if isinstance(job.status, JobStatus) else str(job.status)

            res = await self.client.update(
                self.table,
                data=update_data,
                params={"id": f"eq.{existing.id}"},
            )
            if res:
                return self._from_db_row(res[0])
            return existing

        payload = self._to_db_payload(job)
        res = await self.client.insert(self.table, payload)
        if res:
            return self._from_db_row(res[0])
        return job

    async def get_by_id(self, job_id: UUID) -> Optional[Job]:
        res = await self.client.select(self.table, params={"id": f"eq.{job_id}"})
        if res:
            return self._from_db_row(res[0])
        return None

    async def get_by_platform_and_external_id(self, platform: str, external_id: str) -> Optional[Job]:
        res = await self.client.select(
            self.table,
            params={
                "platform": f"eq.{platform}",
                "external_id": f"eq.{external_id}",
            },
        )
        if res:
            return self._from_db_row(res[0])
        return None

    async def get_by_canonical_key(self, canonical_key: str) -> List[Job]:
        res = await self.client.select(
            self.table,
            params={"canonical_key": f"eq.{canonical_key}"},
        )
        return [self._from_db_row(r) for r in res]

    async def list_jobs(
        self,
        platform: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Job]:
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "order": "first_seen_at.desc",
        }
        if platform:
            params["platform"] = f"eq.{platform}"
        if status:
            params["status"] = f"eq.{status.value}"

        res = await self.client.select(self.table, params=params)
        return [self._from_db_row(r) for r in res]

    async def count(
        self,
        platform: Optional[str] = None,
        status: Optional[JobStatus] = None,
    ) -> int:
        params: Dict[str, Any] = {"select": "id"}
        if platform:
            params["platform"] = f"eq.{platform}"
        if status:
            params["status"] = f"eq.{status.value}"

        res = await self.client.select(self.table, params=params)
        return len(res)

    async def update_score(
        self,
        job_id: UUID,
        score: float,
        score_breakdown: Dict[str, Any],
        status: Optional[JobStatus] = None,
    ) -> Optional[Job]:
        update_data: Dict[str, Any] = {
            "score": score,
            "score_breakdown": score_breakdown,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if status:
            update_data["status"] = status.value

        res = await self.client.update(
            self.table,
            data=update_data,
            params={"id": f"eq.{job_id}"},
        )
        if res:
            return self._from_db_row(res[0])
        return None
