"""Supabase-backed implementation of ApplicationRepository (Phase 2.2).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 13, Section 14)
- worker/application/repository.py (ApplicationRepository Protocol)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from worker.application.exceptions import (
    ApplicationNotFoundError,
    DuplicateApplicationError,
    IdempotencyConflictError,
)
from worker.application.models import Application, ApplicationStatus
from worker.persistence.exceptions import DuplicateRecordError
from worker.persistence.supabase_client import SupabaseClient

logger = logging.getLogger("worker.persistence.application_repository")


class SupabaseApplicationRepository:
    """Production PostgreSQL application repository backed by Supabase PostgREST."""

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client
        self.table = "applications"

    def _to_db_payload(self, app: Application) -> Dict[str, Any]:
        """Convert Application domain model to PostgreSQL applications table row."""
        return {
            "id": str(app.id),
            "job_id": str(app.job_id),
            "user_id": str(app.user_id),
            "platform": app.platform,
            "external_id": app.external_id,
            "run_id": str(app.run_id) if app.run_id else None,
            "profile_version": app.profile_version,
            "resume_version": app.resume_version,
            "autonomy_level": app.autonomy_level.value,
            "status": app.status.value,
            "fields_filled": app.fields_filled,
            "evidence_ref": app.evidence_ref,
            "idempotency_key": app.idempotency_key,
            "error": app.error,
            "applied_at": app.applied_at.isoformat() if app.applied_at else None,
            "created_at": app.created_at.isoformat() if app.created_at else None,
            "updated_at": app.updated_at.isoformat() if app.updated_at else None,
        }

    def _from_db_row(self, row: Dict[str, Any]) -> Application:
        """Convert PostgreSQL row dictionary to Application domain model."""
        return Application.model_validate(row)

    async def create(self, application: Application) -> Application:
        payload = self._to_db_payload(application)
        try:
            res = await self.client.insert(self.table, payload)
            if res:
                return self._from_db_row(res[0])
            return application
        except DuplicateRecordError as e:
            # Check if idempotency conflict or duplicate application
            err_msg = str(e).lower()
            if "uq_applications_idempotency" in err_msg or "idempotency_key" in err_msg:
                # Check if it is replay for same user and job
                existing = await self.get_by_idempotency_key(application.idempotency_key)
                if existing and existing.user_id == application.user_id and existing.job_id == application.job_id:
                    return existing
                raise IdempotencyConflictError(application.idempotency_key)
            raise DuplicateApplicationError(str(application.user_id), str(application.job_id))

    async def get_by_id(self, application_id: UUID) -> Optional[Application]:
        res = await self.client.select(self.table, params={"id": f"eq.{application_id}"})
        if res:
            return self._from_db_row(res[0])
        return None

    async def get_by_user_and_job(self, user_id: UUID, job_id: UUID) -> Optional[Application]:
        res = await self.client.select(
            self.table,
            params={
                "user_id": f"eq.{user_id}",
                "job_id": f"eq.{job_id}",
            },
        )
        if res:
            return self._from_db_row(res[0])
        return None

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Application]:
        res = await self.client.select(
            self.table,
            params={"idempotency_key": f"eq.{idempotency_key}"},
        )
        if res:
            return self._from_db_row(res[0])
        return None

    async def update(self, application: Application) -> Application:
        payload = self._to_db_payload(application)
        res = await self.client.update(
            self.table,
            data=payload,
            params={"id": f"eq.{application.id}"},
        )
        if not res:
            raise ApplicationNotFoundError(str(application.id))
        return self._from_db_row(res[0])

    async def list_by_status(
        self,
        status: ApplicationStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Application]:
        res = await self.client.select(
            self.table,
            params={
                "status": f"eq.{status.value}",
                "limit": limit,
                "offset": offset,
                "order": "created_at.desc",
            },
        )
        return [self._from_db_row(r) for r in res]

    async def list_by_user(
        self,
        user_id: UUID,
        status: Optional[ApplicationStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Application]:
        params: Dict[str, Any] = {
            "user_id": f"eq.{user_id}",
            "limit": limit,
            "offset": offset,
            "order": "created_at.desc",
        }
        if status:
            params["status"] = f"eq.{status.value}"

        res = await self.client.select(self.table, params=params)
        return [self._from_db_row(r) for r in res]

    async def count(
        self,
        status: Optional[ApplicationStatus] = None,
        user_id: Optional[UUID] = None,
    ) -> int:
        params: Dict[str, Any] = {"select": "id"}
        if status:
            params["status"] = f"eq.{status.value}"
        if user_id:
            params["user_id"] = f"eq.{user_id}"

        # In PostgREST, counting can be retrieved by range header or returning rows
        res = await self.client.select(self.table, params=params)
        return len(res)
