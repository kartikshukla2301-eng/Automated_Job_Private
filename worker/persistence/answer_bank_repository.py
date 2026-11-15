"""Supabase-backed implementation of AnswerBankRepository (Phase 2.2).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 7, Section 14)
- worker/answers/repository.py (AnswerBankRepository Protocol)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from worker.answers.exceptions import AnswerNotFoundError, InvalidAnswerEntryError
from worker.answers.models import AnswerBankEntry
from worker.persistence.supabase_client import SupabaseClient

logger = logging.getLogger("worker.persistence.answer_bank_repository")


class SupabaseAnswerBankRepository:
    """Production Answer Bank repository backed by Supabase PostgREST."""

    def __init__(self, client: SupabaseClient, user_id: Optional[UUID] = None) -> None:
        self.client = client
        self.user_id = user_id or uuid4()
        self.table = "answer_bank"

    def _to_db_payload(self, entry: AnswerBankEntry) -> Dict[str, Any]:
        return {
            "id": str(uuid4()),
            "user_id": str(self.user_id),
            "key": entry.key.strip().lower(),
            "category": entry.category.value if hasattr(entry.category, "value") else str(entry.category),
            "aliases": entry.aliases,
            "variants": entry.variants,
            "type": entry.type.value if hasattr(entry.type, "value") else str(entry.type),
            "value": str(entry.value),
            "option_mapping": entry.option_mapping,
            "scope": entry.scope.strip().lower(),
            "policy": entry.policy.value if hasattr(entry.policy, "value") else str(entry.policy),
            "source": entry.source.value if hasattr(entry.source, "value") else str(entry.source),
            "confidence": float(entry.confidence),
            "needs_review": entry.needs_review,
            "last_confirmed_at": entry.last_confirmed_at.isoformat() if entry.last_confirmed_at else None,
            "valid_until": entry.valid_until.isoformat() if entry.valid_until else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _from_db_row(self, row: Dict[str, Any]) -> AnswerBankEntry:
        return AnswerBankEntry.model_validate(row)

    def add(self, entry: AnswerBankEntry) -> None:
        """Add or update an Answer Bank entry synchronously (dispatches async task)."""
        if not entry.key:
            raise InvalidAnswerEntryError("Cannot add AnswerBankEntry with empty key.")

        payload = self._to_db_payload(entry)
        norm_key = entry.key.strip().lower()
        norm_scope = entry.scope.strip().lower()

        # Check existing
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _do_add():
            existing = await self.client.select(
                self.table,
                params={
                    "user_id": f"eq.{self.user_id}",
                    "key": f"eq.{norm_key}",
                    "scope": f"eq.{norm_scope}",
                },
            )
            if existing:
                await self.client.update(
                    self.table,
                    data=payload,
                    params={
                        "user_id": f"eq.{self.user_id}",
                        "key": f"eq.{norm_key}",
                        "scope": f"eq.{norm_scope}",
                    },
                )
            else:
                await self.client.insert(self.table, payload)

        if loop.is_running():
            asyncio.create_task(_do_add())
        else:
            loop.run_until_complete(_do_add())

    def update(self, entry: AnswerBankEntry) -> None:
        """Update an existing entry."""
        if not entry.key:
            raise InvalidAnswerEntryError("Cannot update AnswerBankEntry with empty key.")

        norm_key = entry.key.strip().lower()
        norm_scope = entry.scope.strip().lower()
        payload = self._to_db_payload(entry)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _do_update():
            res = await self.client.update(
                self.table,
                data=payload,
                params={
                    "user_id": f"eq.{self.user_id}",
                    "key": f"eq.{norm_key}",
                    "scope": f"eq.{norm_scope}",
                },
            )
            if not res:
                raise AnswerNotFoundError(f"Answer for '{norm_key}' in scope '{norm_scope}' not found.")

        if loop.is_running():
            asyncio.create_task(_do_update())
        else:
            loop.run_until_complete(_do_update())

    def get(self, key: str, scope: str = "global") -> Optional[AnswerBankEntry]:
        norm_key = key.strip().lower()
        norm_scope = scope.strip().lower()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _do_get():
            res = await self.client.select(
                self.table,
                params={
                    "user_id": f"eq.{self.user_id}",
                    "key": f"eq.{norm_key}",
                    "scope": f"eq.{norm_scope}",
                },
            )
            if res:
                return self._from_db_row(res[0])
            return None

        if loop.is_running():
            # If inside existing loop (e.g. test), create future or task
            future = asyncio.run_coroutine_threadsafe(_do_get(), loop)
            return future.result()
        return loop.run_until_complete(_do_get())

    def search_by_alias(self, query: str, scope: Optional[str] = None) -> List[AnswerBankEntry]:
        clean_q = query.strip().lower()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _do_search():
            params: Dict[str, Any] = {"user_id": f"eq.{self.user_id}"}
            if scope:
                params["scope"] = f"eq.{scope.strip().lower()}"
            res = await self.client.select(self.table, params=params)
            matches = []
            for r in res:
                entry = self._from_db_row(r)
                if clean_q in [a.lower() for a in entry.aliases] or clean_q in [v.lower() for v in entry.variants]:
                    matches.append(entry)
            return matches

        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_do_search(), loop)
            return future.result()
        return loop.run_until_complete(_do_search())

    def list_by_scope(self, scope: str) -> List[AnswerBankEntry]:
        norm_scope = scope.strip().lower()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _do_list():
            res = await self.client.select(
                self.table,
                params={
                    "user_id": f"eq.{self.user_id}",
                    "scope": f"eq.{norm_scope}",
                },
            )
            return [self._from_db_row(r) for r in res]

        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_do_list(), loop)
            return future.result()
        return loop.run_until_complete(_do_list())

    def mark_needs_review(self, key: str, scope: str = "global") -> None:
        norm_key = key.strip().lower()
        norm_scope = scope.strip().lower()

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _do_mark():
            await self.client.update(
                self.table,
                data={"needs_review": True, "updated_at": datetime.now(timezone.utc).isoformat()},
                params={
                    "user_id": f"eq.{self.user_id}",
                    "key": f"eq.{norm_key}",
                    "scope": f"eq.{norm_scope}",
                },
            )

        if loop.is_running():
            asyncio.create_task(_do_mark())
        else:
            loop.run_until_complete(_do_mark())

    def list_all(self) -> List[AnswerBankEntry]:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _do_all():
            res = await self.client.select(
                self.table,
                params={"user_id": f"eq.{self.user_id}"},
            )
            return [self._from_db_row(r) for r in res]

        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(_do_all(), loop)
            return future.result()
        return loop.run_until_complete(_do_all())
