"""Supabase-backed implementation of ApplicationEventRepository (Phase 2.2).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 13, Section 14)
- worker/application/repository.py (ApplicationEventRepository Protocol)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

from worker.application.models import ApplicationEvent
from worker.persistence.supabase_client import SupabaseClient

logger = logging.getLogger("worker.persistence.event_repository")


class SupabaseApplicationEventRepository:
    """Production append-only audit event repository backed by Supabase PostgREST."""

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client
        self.table = "application_events"

    def _to_db_payload(self, event: ApplicationEvent) -> Dict[str, Any]:
        return {
            "id": str(event.id),
            "application_id": str(event.application_id),
            "event_type": event.event_type,
            "previous_status": event.previous_status.value if event.previous_status else None,
            "new_status": event.new_status.value if event.new_status else None,
            "reason": event.reason,
            "triggering_component": event.triggering_component,
            "run_id": str(event.run_id) if event.run_id else None,
            "payload": event.payload,
            "timestamp": event.timestamp.isoformat(),
        }

    def _from_db_row(self, row: Dict[str, Any]) -> ApplicationEvent:
        return ApplicationEvent.model_validate(row)

    async def append_event(self, event: ApplicationEvent) -> ApplicationEvent:
        payload = self._to_db_payload(event)
        res = await self.client.insert(self.table, payload)
        if res:
            return self._from_db_row(res[0])
        return event

    async def list_by_application_id(self, application_id: UUID) -> List[ApplicationEvent]:
        res = await self.client.select(
            self.table,
            params={
                "application_id": f"eq.{application_id}",
                "order": "timestamp.asc",
            },
        )
        return [self._from_db_row(r) for r in res]
