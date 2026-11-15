"""Application and ApplicationEvent repository protocols and in-memory implementations.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 13, 14)
- migrations/001_initial_schema.sql (applications, application_events schemas)
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, List, Optional, Protocol, Set, Tuple, runtime_checkable
from uuid import UUID

from worker.application.exceptions import (
    ApplicationNotFoundError,
    DuplicateApplicationError,
    IdempotencyConflictError,
)
from worker.application.models import (
    Application,
    ApplicationEvent,
    ApplicationStatus,
)


@runtime_checkable
class ApplicationRepository(Protocol):
    """Protocol defining the repository contract for Application persistence."""

    async def create(self, application: Application) -> Application:
        """Create a new Application record.

        Enforces:
        - UNIQUE(user_id, job_id)
        - UNIQUE(idempotency_key)
        """
        ...

    async def get_by_id(self, application_id: UUID) -> Optional[Application]:
        """Retrieve application by primary UUID."""
        ...

    async def get_by_user_and_job(self, user_id: UUID, job_id: UUID) -> Optional[Application]:
        """Retrieve application by unique constraint (user_id, job_id)."""
        ...

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Application]:
        """Retrieve application by unique constraint idempotency_key."""
        ...

    async def update(self, application: Application) -> Application:
        """Update existing Application record."""
        ...

    async def list_by_status(
        self,
        status: ApplicationStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Application]:
        """List applications matching a specific status."""
        ...

    async def list_by_user(
        self,
        user_id: UUID,
        status: Optional[ApplicationStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Application]:
        """List applications for a specific user, with optional status filter."""
        ...

    async def count(
        self,
        status: Optional[ApplicationStatus] = None,
        user_id: Optional[UUID] = None,
    ) -> int:
        """Count applications matching optional filters."""
        ...


@runtime_checkable
class ApplicationEventRepository(Protocol):
    """Protocol defining the repository contract for append-only audit events."""

    async def append_event(self, event: ApplicationEvent) -> ApplicationEvent:
        """Append an immutable audit event."""
        ...

    async def list_by_application_id(self, application_id: UUID) -> List[ApplicationEvent]:
        """Retrieve audit history for an application ordered chronologically."""
        ...


class InMemoryApplicationRepository:
    """Thread-safe, deterministic in-memory ApplicationRepository implementation."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._applications: Dict[UUID, Application] = {}
        self._user_job_index: Dict[Tuple[UUID, UUID], UUID] = {}
        self._idempotency_index: Dict[str, UUID] = {}

    async def create(self, application: Application) -> Application:
        async with self._lock:
            user_job_key = (application.user_id, application.job_id)

            # Idempotency check: if identical idempotency_key exists for the same user and job
            if application.idempotency_key in self._idempotency_index:
                existing_id = self._idempotency_index[application.idempotency_key]
                existing_app = self._applications[existing_id]
                if existing_app.user_id == application.user_id and existing_app.job_id == application.job_id:
                    # Idempotent replay: return existing record safely
                    return existing_app
                raise IdempotencyConflictError(application.idempotency_key)

            # Unique constraint check: UNIQUE(user_id, job_id)
            if user_job_key in self._user_job_index:
                raise DuplicateApplicationError(str(application.user_id), str(application.job_id))

            # Store application and update indexes
            self._applications[application.id] = application
            self._user_job_index[user_job_key] = application.id
            self._idempotency_index[application.idempotency_key] = application.id
            return application

    async def get_by_id(self, application_id: UUID) -> Optional[Application]:
        async with self._lock:
            return self._applications.get(application_id)

    async def get_by_user_and_job(self, user_id: UUID, job_id: UUID) -> Optional[Application]:
        async with self._lock:
            app_id = self._user_job_index.get((user_id, job_id))
            if app_id:
                return self._applications.get(app_id)
            return None

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Application]:
        async with self._lock:
            app_id = self._idempotency_index.get(idempotency_key)
            if app_id:
                return self._applications.get(app_id)
            return None

    async def update(self, application: Application) -> Application:
        async with self._lock:
            if application.id not in self._applications:
                raise ApplicationNotFoundError(str(application.id))
            self._applications[application.id] = application
            return application

    async def list_by_status(
        self,
        status: ApplicationStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Application]:
        async with self._lock:
            matches = [a for a in self._applications.values() if a.status == status]
            matches.sort(key=lambda a: (a.created_at, str(a.id)), reverse=True)
            return matches[offset : offset + limit]

    async def list_by_user(
        self,
        user_id: UUID,
        status: Optional[ApplicationStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Application]:
        async with self._lock:
            matches = [
                a for a in self._applications.values()
                if a.user_id == user_id and (status is None or a.status == status)
            ]
            matches.sort(key=lambda a: (a.created_at, str(a.id)), reverse=True)
            return matches[offset : offset + limit]

    async def count(
        self,
        status: Optional[ApplicationStatus] = None,
        user_id: Optional[UUID] = None,
    ) -> int:
        async with self._lock:
            count = 0
            for a in self._applications.values():
                if user_id and a.user_id != user_id:
                    continue
                if status and a.status != status:
                    continue
                count += 1
            return count


class InMemoryApplicationEventRepository:
    """Thread-safe, append-only in-memory ApplicationEventRepository."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._events: List[ApplicationEvent] = []
        self._app_event_index: Dict[UUID, List[ApplicationEvent]] = defaultdict(list)

    async def append_event(self, event: ApplicationEvent) -> ApplicationEvent:
        async with self._lock:
            self._events.append(event)
            self._app_event_index[event.application_id].append(event)
            return event

    async def list_by_application_id(self, application_id: UUID) -> List[ApplicationEvent]:
        async with self._lock:
            # Return chronologically sorted copy
            events = list(self._app_event_index.get(application_id, []))
            events.sort(key=lambda e: e.timestamp)
            return events
