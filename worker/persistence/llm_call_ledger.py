"""Supabase-backed LLMCallLedger: durable AI call/cost audit trail (Phase 4.5).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14 `llm_calls`)
- docs/BUILD_RULES.md ("Track input/output/total tokens and costs ... Never fabricate
  usage or prices; clearly label estimates/unknowns.")

Why this exists: `FileLLMCallLedger` (worker/core/llm_gateway.py) already documents that
it is single-process only and that "multi-process deployments must use PostgreSQL-backed
accounting (migrations/001_initial_schema.sql:llm_calls)" — this module is that backend,
so every LLM call's model, task, tokens, cost, latency, cache status and outcome lands in
the real database and can be queried directly, not just in a local JSONL file.

Design notes:
- `LLMCallLedger.record_call()` is a synchronous method, called directly (not awaited)
  from the locked, unmodified `LLMGateway.execute()`. To honor that exact contract without
  touching `llm_gateway.py`, this ledger uses a plain synchronous `httpx.Client` for the
  REST insert rather than requiring the gateway to become async-aware of its ledger.
- `record_call()` never raises: a logging/telemetry failure must never break the LLM
  response it is trying to record. Failures are logged and swallowed.
- `count_daily_calls()`/`get_daily_cost_usd()` DO raise on failure (`InvalidSafetyStateError`),
  matching `FileLLMCallLedger`'s existing fail-closed behavior on corrupted/unreadable state,
  because these feed the daily budget gate and must never silently be treated as "zero calls
  so far today".
- Column mapping: the locked `llm_calls` table only has
  run_id/task/model/tokens/cost_usd/latency_ms/cache_hit/outcome/created_at. It has no
  application_id, cost_provenance, or pricing_source columns. Those `LLMCallRecord` fields
  are therefore not persisted to Supabase (adding columns would be a schema change requiring
  an explicit decision per AGENTS.md/docs/DECISIONS.md, not done here). `cost_usd` is sent as
  SQL NULL (the column is nullable) whenever the in-process cost is unknown, rather than ever
  defaulting an unknown cost to 0 — the one piece of cost-provenance information the schema
  can still represent honestly.
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, time, timezone
from typing import Dict, List, Tuple

import httpx

from worker.core.exceptions import InvalidSafetyStateError
from worker.core.llm_gateway import LLMCallRecord

logger = logging.getLogger("worker.persistence.llm_call_ledger")

# Outcomes that count toward the daily call budget — mirrors InMemoryLLMCallLedger /
# FileLLMCallLedger exactly so budget accounting is identical regardless of backend.
_BUDGET_COUNTED_OUTCOMES = ("SUCCESS", "DEGRADED", "ERROR", "TIMEOUT", "PROVIDER_ERROR")


class SupabaseLLMCallLedger:
    """Durable, queryable LLM call ledger backed by Supabase's `llm_calls` table."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
        transport: "httpx.BaseTransport | None" = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.rest_url = f"{self.base_url}/rest/v1/llm_calls"
        self.api_key = api_key
        self.timeout = timeout
        self._transport = transport  # test-only hook; None uses httpx's real transport
        self._lock = threading.Lock()

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout, transport=self._transport)

    def _headers(self, prefer: str = "return=minimal") -> Dict[str, str]:
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": prefer,
        }

    def record_call(self, record: LLMCallRecord) -> None:
        """Persist one LLM call to Supabase. Never raises — logs and swallows failures."""
        payload = {
            "run_id": record.run_id,
            "task": record.task,
            "model": record.model,
            "tokens": {
                "input": record.tokens.get("input"),
                "output": record.tokens.get("output"),
                "total": record.tokens.get("total"),
            },
            "cost_usd": record.cost_usd,  # None -> SQL NULL -> honestly "unknown", never 0
            "latency_ms": record.latency_ms,
            "cache_hit": record.cache_hit,
            "outcome": record.outcome,
            "created_at": record.created_at.astimezone(timezone.utc).isoformat(),
        }
        try:
            with self._lock:
                with self._client() as client:
                    response = client.post(self.rest_url, json=payload, headers=self._headers())
            if response.status_code not in (200, 201, 204):
                logger.warning(
                    "Supabase llm_calls insert failed (HTTP %s): %s",
                    response.status_code,
                    response.text,
                )
        except httpx.HTTPError as exc:
            logger.warning("Supabase llm_calls insert transport error: %s", exc)

    def _day_bounds_iso(self, target_date: date) -> Tuple[str, str]:
        start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)
        return start.isoformat(), end.isoformat()

    def _fetch_day_rows(self, target_date: date) -> List[Dict]:
        start_iso, end_iso = self._day_bounds_iso(target_date)
        params = {
            "select": "cost_usd,outcome,created_at",
            "created_at": [f"gte.{start_iso}", f"lte.{end_iso}"],
        }
        try:
            with self._client() as client:
                response = client.get(self.rest_url, params=params, headers=self._headers("return=representation"))
        except httpx.HTTPError as exc:
            raise InvalidSafetyStateError(
                f"Supabase llm_calls query transport error for {target_date}: {exc}"
            ) from exc

        if response.status_code != 200:
            raise InvalidSafetyStateError(
                f"Supabase llm_calls query failed for {target_date} (HTTP {response.status_code}): "
                f"{response.text}"
            )
        try:
            return response.json()
        except Exception as exc:
            raise InvalidSafetyStateError(
                f"Supabase llm_calls query returned non-JSON payload for {target_date}: {exc}"
            ) from exc

    def count_daily_calls(self, target_date: date) -> int:
        rows = self._fetch_day_rows(target_date)
        return sum(1 for r in rows if r.get("outcome") in _BUDGET_COUNTED_OUTCOMES)

    def get_daily_cost_usd(self, target_date: date) -> Tuple[float, int]:
        rows = self._fetch_day_rows(target_date)
        known_cost = 0.0
        unknown_count = 0
        for r in rows:
            cost = r.get("cost_usd")
            if cost is not None:
                known_cost += float(cost)
            else:
                unknown_count += 1
        return known_cost, unknown_count
