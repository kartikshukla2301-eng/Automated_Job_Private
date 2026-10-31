"""Central LLM Gateway with OpenRouter integration, cost tracking, caching, and circuit breaker.

AUTHORITY:
docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 14, 15, Appendix B).
docs/DECISIONS.md (AD-003, AD-007, AD-009).
"""

import asyncio
from decimal import Decimal
from enum import Enum
import hashlib
import json
import logging
import math
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Protocol, Tuple, Union
import uuid
from datetime import date, datetime, timezone

import httpx
from pydantic import BaseModel, Field

from services.api.config import LLMConfig
from worker.core.exceptions import (
    InvalidSafetyStateError,
    LLMAuthenticationError,
    LLMBudgetExceededError,
    LLMCircuitBreakerOpenError,
    LLMDegradedModeError,
    LLMGatewayError,
    LLMMalformedResponseError,
    LLMProviderError,
    LLMTimeoutError,
)

logger = logging.getLogger("worker.core.llm_gateway")

CostProvenance = Literal["reported", "estimated", "unknown"]


# ==============================================================================
# 1. Prompt Injection Defense Helper (Architecture Section 15, RC-4)
# ==============================================================================

# Dangerous characters regex: ASCII controls, zero-width chars, bidi overrides, format characters
_DANGEROUS_CHARS_REGEX = re.compile(
    r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F"  # ASCII controls
    r"\u200B-\u200F"  # Zero-width spaces, LRM, RLM
    r"\u202A-\u202E"  # Bidi overrides and embedding (LRE, RLE, PDF, LRO, RLO)
    r"\u2060-\u2069"  # Word joiner, invisible operators, bidi isolates (LRI, RLI, FSI, PDI)
    r"\uFEFF"  # Byte-order mark / Zero-width no-break space
    r"\uFFF9-\uFFFB]"  # Interlinear annotation controls
)
_UNTRUSTED_DELIMITER_REGEX = re.compile(r"<\s*/?\s*untrusted_content\b[^>]*>", re.IGNORECASE)


def sanitize_untrusted_prompt_data(content: str, max_chars: int = 4000) -> str:
    """Sanitize, neutralize delimiters, and delimit untrusted external content.

    ARCHITECTURAL RULES (RC-4):
    - External job text is data, never instruction.
    - Strips invisible formatting, bidi overrides, and control characters while preserving readable Unicode text.
    - Neutralizes embedded <untrusted_content> tags to prevent delimiter breakout.
    - Caps maximum input length.
    - Wraps data in explicit boundary delimiters.
    """
    if not content:
        return "<untrusted_content></untrusted_content>"

    # 1. Strip dangerous control and invisible formatting characters
    clean = _DANGEROUS_CHARS_REGEX.sub("", content)

    # 2. Neutralize literal opening/closing delimiter tags inside untrusted text before wrapping
    clean = _UNTRUSTED_DELIMITER_REGEX.sub(
        lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"),
        clean,
    )

    # 3. Cap maximum input length
    if len(clean) > max_chars:
        clean = clean[:max_chars] + "... [TRUNCATED]"

    return f"<untrusted_content>\n{clean}\n</untrusted_content>"


# ==============================================================================
# 2. Typed Request and Response Models
# ==============================================================================


class LLMTokenUsage(BaseModel):
    """Token accounting breakdown."""

    input_tokens: Optional[int] = Field(default=None, description="Prompt input tokens")
    output_tokens: Optional[int] = Field(default=None, description="Completion output tokens")
    total_tokens: Optional[int] = Field(default=None, description="Total tokens consumed")


class LLMRequest(BaseModel):
    """Standardized runtime LLM request model."""

    task: str = Field(..., description="Task or purpose (e.g. unknown_question, form_field_matching)")
    messages: List[Dict[str, str]] = Field(..., description="Chat completion messages")
    model: Optional[str] = Field(default=None, description="Explicit model ID; defaults to config chain")
    run_id: Optional[str] = Field(default=None, description="Execution run correlation ID")
    application_id: Optional[str] = Field(default=None, description="Application correlation ID")
    timeout_seconds: float = Field(default=30.0, ge=1.0, description="Request timeout in seconds")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Maximum completion tokens")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="Sampling temperature")
    cache_eligible: bool = Field(default=True, description="Whether response can be retrieved/cached")
    profile_version: Optional[str] = Field(
        default=None, description="Candidate profile version hash for cache scoping"
    )
    cache_scope: Optional[str] = Field(
        default=None, description="Optional user/tenant/context isolation scope for caching"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")


class LLMResponse(BaseModel):
    """Standardized auditable runtime LLM response model."""

    content: str = Field(..., description="Generated text content from LLM")
    model: str = Field(..., description="Model ID actually used")
    task: str = Field(..., description="Task or purpose category")
    tokens: LLMTokenUsage = Field(default_factory=LLMTokenUsage, description="Token consumption")
    cost_usd: Optional[float] = Field(
        default=None, description="Total cost in USD (None if unknown; never assumed 0.0)"
    )
    input_cost_usd: Optional[float] = Field(default=None, description="Input cost component in USD")
    output_cost_usd: Optional[float] = Field(default=None, description="Output cost component in USD")
    cost_provenance: CostProvenance = Field(
        default="unknown", description="Cost source category: reported, estimated, or unknown"
    )
    pricing_source: Optional[str] = Field(
        default=None, description="Pricing origin reference or model table key"
    )
    latency_ms: int = Field(default=0, ge=0, description="Round-trip latency in milliseconds")
    cache_hit: bool = Field(default=False, description="Whether response was served from cache")
    run_id: Optional[str] = Field(default=None, description="Associated execution run ID")
    application_id: Optional[str] = Field(default=None, description="Associated application ID")
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the completion",
    )
    degraded_mode: bool = Field(
        default=False, description="True if response was produced by fallback/degraded mode"
    )
    error_reason: Optional[str] = Field(
        default=None, description="Failure reason if degraded mode or fallback occurred"
    )


# ==============================================================================
# 3. Durable Call Accounting and Ledger (Architecture Section 14: llm_calls)
# ==============================================================================


class LLMCallRecord(BaseModel):
    """Audit record corresponding to Section 14 llm_calls schema."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: Optional[str] = None
    application_id: Optional[str] = None
    task: str
    model: str
    tokens: Dict[str, Optional[int]]
    cost_usd: Optional[float] = None
    cost_provenance: str = "unknown"
    latency_ms: int
    cache_hit: bool
    outcome: str = Field(..., description="SUCCESS, CACHE_HIT, DEGRADED, ERROR, TIMEOUT, PROVIDER_ERROR")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LLMCallLedger(Protocol):
    """Interface for recording and aggregating LLM call telemetry and quotas."""

    def record_call(self, record: LLMCallRecord) -> None: ...

    def count_daily_calls(self, target_date: date) -> int: ...

    def get_daily_cost_usd(self, target_date: date) -> Tuple[float, int]:
        """Return (sum_of_known_costs, count_of_unknown_costs)."""
        ...


class InMemoryLLMCallLedger:
    """In-memory call ledger for isolated unit testing.

    CONCURRENCY & PROCESS GUARANTEES:
    - Thread-safe: In-process read/write operations are synchronized with threading.Lock().
    - In-memory only: Resets when process terminates.
    """

    def __init__(self) -> None:
        self._records: List[LLMCallRecord] = []
        self._lock = threading.Lock()

    def record_call(self, record: LLMCallRecord) -> None:
        with self._lock:
            self._records.append(record)

    def count_daily_calls(self, target_date: date) -> int:
        with self._lock:
            return sum(
                1
                for r in self._records
                if r.created_at.astimezone(timezone.utc).date() == target_date
                and r.outcome in ("SUCCESS", "DEGRADED", "ERROR", "TIMEOUT", "PROVIDER_ERROR")
            )

    def get_daily_cost_usd(self, target_date: date) -> Tuple[float, int]:
        with self._lock:
            known_cost = 0.0
            unknown_count = 0
            for r in self._records:
                if r.created_at.astimezone(timezone.utc).date() == target_date:
                    if r.cost_usd is not None:
                        known_cost += r.cost_usd
                    elif r.cost_provenance == "unknown":
                        unknown_count += 1
            return known_cost, unknown_count


class FileLLMCallLedger:
    """Durable append-only JSONL call ledger surviving worker restarts.

    CONCURRENCY & PROCESS GUARANTEES:
    - Thread-safe: In-process read/write operations are synchronized with threading.Lock().
    - Single-process only: FileLLMCallLedger assumes a single worker/API process owns the ledger file.
      Inter-process synchronization across multiple OS processes is NOT supported. Multi-process
      deployments must use PostgreSQL-backed accounting (migrations/001_initial_schema.sql:llm_calls).
    - Fail-closed durability: Corrupted JSONL records raise InvalidSafetyStateError rather than
      silently skipping lines or resetting quotas.
    """

    def __init__(self, file_path: Union[str, Path]) -> None:
        self.file_path = Path(file_path)
        self._lock = threading.Lock()

    def record_call(self, record: LLMCallRecord) -> None:
        with self._lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(record.model_dump_json() + "\n")

    def _read_records(self) -> List[LLMCallRecord]:
        with self._lock:
            if not self.file_path.exists():
                return []
            records = []
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    clean = line.strip()
                    if not clean:
                        continue
                    try:
                        records.append(LLMCallRecord.model_validate_json(clean))
                    except Exception as exc:
                        raise InvalidSafetyStateError(
                            f"Corrupted LLM ledger at line {line_no} in '{self.file_path}': {exc}"
                        ) from exc
            return records

    def count_daily_calls(self, target_date: date) -> int:
        records = self._read_records()
        return sum(
            1
            for r in records
            if r.created_at.astimezone(timezone.utc).date() == target_date
            and r.outcome in ("SUCCESS", "DEGRADED", "ERROR", "TIMEOUT", "PROVIDER_ERROR")
        )

    def get_daily_cost_usd(self, target_date: date) -> Tuple[float, int]:
        records = self._read_records()
        known_cost = 0.0
        unknown_count = 0
        for r in records:
            if r.created_at.astimezone(timezone.utc).date() == target_date:
                if r.cost_usd is not None:
                    known_cost += r.cost_usd
                elif r.cost_provenance == "unknown":
                    unknown_count += 1
        return known_cost, unknown_count


# ==============================================================================
# 4. Safe Response Cache (Architecture Section 15, Paragraph 546)
# ==============================================================================


def compute_cache_key(
    task: str,
    model: str,
    messages: List[Dict[str, str]],
    profile_version: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    cache_scope: Optional[str] = None,
) -> str:
    """Generate deterministic, sanitized SHA-256 cache key without logging raw PII.

    Includes all generation parameters affecting output: task, model, messages, profile_version,
    temperature, max_tokens, and cache_scope for authorization/candidate isolation.
    """
    payload = {
        "task": task.strip().lower(),
        "model": model.strip().lower(),
        "messages": messages,
        "profile_version": profile_version or "no_profile",
        "temperature": round(float(temperature), 4),
        "max_tokens": max_tokens,
        "cache_scope": cache_scope or "default",
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"llm_cache:{task}:{digest}"


class LLMCache(Protocol):
    """Interface for LLM completion caching."""

    def get(self, key: str, now: Optional[datetime] = None) -> Optional[LLMResponse]: ...

    def set(
        self,
        key: str,
        response: LLMResponse,
        ttl_seconds: int = 86400,
        now: Optional[datetime] = None,
    ) -> None: ...

    def clear(self) -> None: ...


class InMemoryLLMCache:
    """In-memory cache with TTL expiration for testing."""

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[LLMResponse, datetime]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, now: Optional[datetime] = None) -> Optional[LLMResponse]:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            response, expires_at = entry
            if current >= expires_at:
                del self._store[key]
                return None
            return response.model_copy(deep=True)

    def set(
        self,
        key: str,
        response: LLMResponse,
        ttl_seconds: int = 86400,
        now: Optional[datetime] = None,
    ) -> None:
        current = now or datetime.now(timezone.utc)
        expires_at = current.fromtimestamp(current.timestamp() + ttl_seconds, tz=timezone.utc)
        with self._lock:
            self._store[key] = (response.model_copy(deep=True), expires_at)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class FileLLMCache:
    """Durable file-backed cache stored in worker/sessions/llm_cache.json.

    Uses unique per-write temporary files and atomic replacement to prevent collisions.
    """

    def __init__(self, file_path: Union[str, Path]) -> None:
        self.file_path = Path(file_path)
        self._lock = threading.Lock()

    def _read_data(self) -> Dict[str, Any]:
        if not self.file_path.exists():
            return {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Corrupted LLM cache file at '%s': %s. Resetting cache.", self.file_path, exc)
            return {}

    def _write_data(self, data: Dict[str, Any]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file_path.with_name(f"{self.file_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp.replace(self.file_path)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise

    def get(self, key: str, now: Optional[datetime] = None) -> Optional[LLMResponse]:
        current_ts = (now or datetime.now(timezone.utc)).timestamp()
        with self._lock:
            data = self._read_data()
            entry = data.get(key)
            if not entry:
                return None
            if current_ts >= entry.get("expires_at", 0):
                del data[key]
                self._write_data(data)
                return None
            return LLMResponse.model_validate(entry["response"])

    def set(
        self,
        key: str,
        response: LLMResponse,
        ttl_seconds: int = 86400,
        now: Optional[datetime] = None,
    ) -> None:
        current_ts = (now or datetime.now(timezone.utc)).timestamp()
        expires_at = current_ts + ttl_seconds
        with self._lock:
            data = self._read_data()
            data[key] = {
                "expires_at": expires_at,
                "response": json.loads(response.model_dump_json()),
            }
            self._write_data(data)

    def clear(self) -> None:
        with self._lock:
            if self.file_path.exists():
                self.file_path.unlink()


# ==============================================================================
# 5. Circuit Breaker (Architecture Section 15, Paragraph 545)
# ==============================================================================


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Deterministic, testable circuit breaker protecting against repeated provider outages."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
        half_open_success_threshold: int = 1,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_success_threshold = half_open_success_threshold
        self.clock = clock or (lambda: datetime.now(timezone.utc))

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_in_flight = 0
        self.opened_at: Optional[datetime] = None
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """Evaluate if an external request is permitted under circuit rules."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            now = self.clock()
            if self.state == CircuitState.OPEN:
                if self.opened_at and (now - self.opened_at).total_seconds() >= self.recovery_timeout_seconds:
                    logger.info("Circuit breaker entering HALF_OPEN for trial probe.")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    self.half_open_in_flight = 1
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_in_flight < self.half_open_success_threshold:
                    self.half_open_in_flight += 1
                    return True
                return False

            return False

    def record_success(self) -> None:
        """Record a successful provider request."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_in_flight > 0:
                    self.half_open_in_flight -= 1
                self.success_count += 1
                if self.success_count >= self.half_open_success_threshold:
                    logger.info("Circuit breaker probe succeeded. Transitioning to CLOSED.")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.opened_at = None
                    self.half_open_in_flight = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self, is_provider_error: bool = True) -> None:
        """Record an operation failure. Ignores caller validation/budget errors."""
        if not is_provider_error:
            with self._lock:
                if self.state == CircuitState.HALF_OPEN and self.half_open_in_flight > 0:
                    self.half_open_in_flight -= 1
            return

        with self._lock:
            now = self.clock()
            if self.state == CircuitState.HALF_OPEN:
                logger.warning("Circuit breaker probe failed in HALF_OPEN. Tripping back to OPEN.")
                self.state = CircuitState.OPEN
                self.opened_at = now
                self.half_open_in_flight = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.failure_threshold:
                    logger.warning(
                        "Circuit breaker threshold reached (%d consecutive failures). Transitioning to OPEN.",
                        self.failure_count,
                    )
                    self.state = CircuitState.OPEN
                    self.opened_at = now

    def release_probe(self) -> None:
        """Release an in-flight probe on cancellation or unexpected error."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN and self.half_open_in_flight > 0:
                self.half_open_in_flight -= 1

    def trip(self, reason: str = "Manual operator trip") -> None:
        """Force the breaker into OPEN state."""
        with self._lock:
            self.state = CircuitState.OPEN
            self.opened_at = self.clock()
            self.half_open_in_flight = 0
            logger.warning("Circuit breaker tripped manually: %s", reason)

    def reset(self) -> None:
        """Reset the breaker to healthy CLOSED state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.half_open_in_flight = 0
            self.opened_at = None


# ==============================================================================
# 6. OpenRouter Async Client
# ==============================================================================


class OpenRouterClient:
    """Asynchronous client communicating exclusively with OpenRouter API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        app_name: str = "AI Job Application Agent",
        site_url: Optional[str] = None,
        pricing_table: Optional[Dict[str, Dict[str, float]]] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.app_name = app_name
        self.site_url = site_url or "https://github.com/job-agent"
        self.pricing_table = pricing_table or {}
        self._external_client = http_client
        self._client: Optional[httpx.AsyncClient] = http_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()
        return self._client

    async def aclose(self) -> None:
        """Cleanly close underlying HTTP client if internally managed."""
        if self._external_client is None and self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def complete(
        self,
        model: str,
        messages: List[Dict[str, str]],
        timeout_seconds: float = 30.0,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
    ) -> Tuple[str, LLMTokenUsage, Optional[float], CostProvenance, Optional[str]]:
        """Dispatch completion to OpenRouter.

        Returns:
            Tuple of (content, tokens, cost_usd, cost_provenance, pricing_source)
        """
        if not self.api_key:
            raise LLMAuthenticationError("OpenRouter API key is not configured.")

        client = await self._get_client()
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            response = await client.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"OpenRouter request timed out after {timeout_seconds}s: {exc}") from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(f"OpenRouter network transport error: {exc}") from exc

        if response.status_code in (401, 403):
            raise LLMAuthenticationError(f"OpenRouter rejected credentials (HTTP {response.status_code}).")

        if response.status_code == 429:
            raise LLMProviderError("OpenRouter rate limit or credit quota exceeded (HTTP 429).")

        if response.status_code >= 500:
            raise LLMProviderError(f"OpenRouter server error (HTTP {response.status_code}): {response.text}")

        if response.status_code != 200:
            raise LLMProviderError(f"OpenRouter unexpected HTTP {response.status_code}: {response.text}")

        try:
            data = response.json()
        except Exception as exc:
            raise LLMMalformedResponseError(f"OpenRouter returned non-JSON payload: {exc}") from exc

        choices = data.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            raise LLMMalformedResponseError("OpenRouter response contains empty or invalid 'choices' list.")

        content = choices[0].get("message", {}).get("content")
        if content is None:
            raise LLMMalformedResponseError("OpenRouter message choices missing 'content' property.")

        # Extract tokens faithfully without fabrication (validate non-negative ints)
        raw_usage = data.get("usage")
        tokens = LLMTokenUsage()
        if isinstance(raw_usage, dict):
            raw_inp = raw_usage.get("prompt_tokens")
            raw_out = raw_usage.get("completion_tokens")
            raw_tot = raw_usage.get("total_tokens")

            if isinstance(raw_inp, int) and not isinstance(raw_inp, bool) and raw_inp >= 0:
                tokens.input_tokens = raw_inp
            if isinstance(raw_out, int) and not isinstance(raw_out, bool) and raw_out >= 0:
                tokens.output_tokens = raw_out
            if isinstance(raw_tot, int) and not isinstance(raw_tot, bool) and raw_tot >= 0:
                tokens.total_tokens = raw_tot

        # Extract or estimate cost honestly (never assume unknown = 0.0)
        cost_usd: Optional[float] = None
        cost_provenance: CostProvenance = "unknown"
        pricing_source: Optional[str] = None

        reported_cost = None
        if isinstance(raw_usage, dict) and "cost" in raw_usage:
            reported_cost = raw_usage.get("cost")
        elif "cost" in data:
            reported_cost = data.get("cost")

        if reported_cost is not None:
            try:
                val = float(reported_cost)
                if math.isfinite(val) and val >= 0.0:
                    cost_usd = val
                    cost_provenance = "reported"
                    pricing_source = "openrouter_api_reported"
                else:
                    logger.warning("Provider reported invalid cost value (%s). Treating as unknown.", reported_cost)
                    cost_usd = None
                    cost_provenance = "unknown"
            except (ValueError, TypeError):
                cost_usd = None
                cost_provenance = "unknown"

        if (
            cost_usd is None
            and model in self.pricing_table
            and tokens.input_tokens is not None
            and tokens.output_tokens is not None
        ):
            rates = self.pricing_table[model]
            try:
                inp_rate = float(rates.get("input_per_million", 0.0))
                out_rate = float(rates.get("output_per_million", 0.0))
                if math.isfinite(inp_rate) and inp_rate >= 0.0 and math.isfinite(out_rate) and out_rate >= 0.0:
                    d_inp = Decimal(str(tokens.input_tokens)) * Decimal(str(inp_rate)) / Decimal("1000000")
                    d_out = Decimal(str(tokens.output_tokens)) * Decimal(str(out_rate)) / Decimal("1000000")
                    calc = float(d_inp + d_out)
                    if math.isfinite(calc) and calc >= 0.0:
                        cost_usd = calc
                        cost_provenance = "estimated"
                        pricing_source = f"config_pricing_table:{model}"
                    else:
                        cost_usd = None
                        cost_provenance = "unknown"
                else:
                    logger.warning(
                        "Configured pricing table for model '%s' contains invalid rates. Treating cost as unknown.",
                        model,
                    )
                    cost_usd = None
                    cost_provenance = "unknown"
            except (ValueError, TypeError):
                cost_usd = None
                cost_provenance = "unknown"

        return content, tokens, cost_usd, cost_provenance, pricing_source


# ==============================================================================
# 7. Central LLM Gateway
# ==============================================================================


class LLMGateway:
    """Central orchestrator for runtime LLM requests.

    Enforces mandatory model routing, usage/cost telemetry, daily budget,
    circuit breaker protection, deduplicating cache, and safe degraded mode.

    CONCURRENCY & PROCESS GUARANTEE:
    - Single-process concurrency: Thread-safe and async-task safe via serialized asyncio dispatch lock.
    - Multi-process note: File-backed ledger and cache are single-process only; multi-process
      deployments require database-backed state (Supabase llm_calls).
    """

    def __init__(
        self,
        client: OpenRouterClient,
        config: LLMConfig,
        ledger: LLMCallLedger,
        cache: Optional[LLMCache] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.client = client
        self.config = config
        self.ledger = ledger
        self.cache = cache
        self.clock = clock or (lambda: datetime.now(timezone.utc))

        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=config.circuit_breaker_failure_threshold,
            recovery_timeout_seconds=config.circuit_breaker_recovery_seconds,
            clock=self.clock,
        )
        self._dispatch_lock: Optional[asyncio.Lock] = None

    @property
    def dispatch_lock(self) -> asyncio.Lock:
        if self._dispatch_lock is None:
            self._dispatch_lock = asyncio.Lock()
        return self._dispatch_lock

    def _has_valid_pricing(self, model: str) -> bool:
        """Verify configured model pricing exists and is valid (AD-009)."""
        rates = self.client.pricing_table.get(model) or self.config.model_pricing.get(model)
        if not rates or not isinstance(rates, dict):
            return False
        try:
            inp = float(rates.get("input_per_million", -1.0))
            out = float(rates.get("output_per_million", -1.0))
            return math.isfinite(inp) and inp >= 0.0 and math.isfinite(out) and out >= 0.0
        except (ValueError, TypeError):
            return False

    def _resolve_model(self, request: LLMRequest) -> str:
        """Select model from explicit request or configured task fallback chain."""
        if request.model:
            return request.model

        chain = self.config.chains.get(request.task)
        if chain and len(chain) > 0:
            return chain[0]

        default_chain = self.config.chains.get("unknown_question", ["meta-llama/llama-3-8b-instruct"])
        return default_chain[0]

    async def execute(
        self,
        request: LLMRequest,
        allow_degraded: bool = True,
    ) -> LLMResponse:
        """Execute a validated runtime LLM request through the gateway.

        Args:
            request: Typed completion request model.
            allow_degraded: If True, returns degraded response when blocked;
                           If False, raises typed gateway exceptions.

        Returns:
            LLMResponse: Auditable completion response.
        """
        model = self._resolve_model(request)
        now = self.clock()

        # 1. Deduplicating Cache Check (Architecture Paragraph 546)
        if request.cache_eligible and self.cache is not None:
            cache_key = compute_cache_key(
                task=request.task,
                model=model,
                messages=request.messages,
                profile_version=request.profile_version,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                cache_scope=request.cache_scope,
            )
            cached = self.cache.get(cache_key, now=now)
            if cached is not None:
                logger.info("LLM Gateway cache hit for task '%s', model '%s'", request.task, model)
                self.ledger.record_call(
                    LLMCallRecord(
                        run_id=request.run_id,
                        application_id=request.application_id,
                        task=request.task,
                        model=model,
                        tokens={
                            "input": cached.tokens.input_tokens,
                            "output": cached.tokens.output_tokens,
                            "total": cached.tokens.total_tokens,
                        },
                        cost_usd=0.0,
                        cost_provenance="reported",
                        latency_ms=0,
                        cache_hit=True,
                        outcome="CACHE_HIT",
                        created_at=now,
                    )
                )
                return cached.model_copy(
                    update={
                        "cache_hit": True,
                        "latency_ms": 0,
                        "executed_at": now,
                        "run_id": request.run_id,
                        "application_id": request.application_id,
                    }
                )

        # 2. Synchronized Quota Reservation and Dispatch
        async with self.dispatch_lock:
            now = self.clock()
            today = now.astimezone(timezone.utc).date()

            # Ensure client pricing table is populated from config if empty
            if not self.client.pricing_table and self.config.model_pricing:
                self.client.pricing_table = self.config.model_pricing

            # Re-check cache under lock in case concurrent task populated it
            if request.cache_eligible and self.cache is not None:
                cache_key = compute_cache_key(
                    task=request.task,
                    model=model,
                    messages=request.messages,
                    profile_version=request.profile_version,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    cache_scope=request.cache_scope,
                )
                cached = self.cache.get(cache_key, now=now)
                if cached is not None:
                    self.ledger.record_call(
                        LLMCallRecord(
                            run_id=request.run_id,
                            application_id=request.application_id,
                            task=request.task,
                            model=model,
                            tokens={
                                "input": cached.tokens.input_tokens,
                                "output": cached.tokens.output_tokens,
                                "total": cached.tokens.total_tokens,
                            },
                            cost_usd=0.0,
                            cost_provenance="reported",
                            latency_ms=0,
                            cache_hit=True,
                            outcome="CACHE_HIT",
                            created_at=now,
                        )
                    )
                    return cached.model_copy(
                        update={
                            "cache_hit": True,
                            "latency_ms": 0,
                            "executed_at": now,
                            "run_id": request.run_id,
                            "application_id": request.application_id,
                        }
                    )

            # Daily Call Budget Check (Architecture Section 15, Paragraph 545)
            daily_calls = self.ledger.count_daily_calls(today)
            if daily_calls >= self.config.daily_call_budget:
                err_msg = (
                    f"Daily LLM call budget exhausted: {daily_calls}/{self.config.daily_call_budget} on {today}"
                )
                logger.warning(err_msg)
                self.ledger.record_call(
                    LLMCallRecord(
                        run_id=request.run_id,
                        application_id=request.application_id,
                        task=request.task,
                        model=model,
                        tokens={"input": None, "output": None, "total": None},
                        cost_usd=None,
                        cost_provenance="unknown",
                        latency_ms=0,
                        cache_hit=False,
                        outcome="BUDGET_EXCEEDED",
                        created_at=now,
                    )
                )
                if allow_degraded:
                    return LLMResponse(
                        content="",
                        model=model,
                        task=request.task,
                        latency_ms=0,
                        cache_hit=False,
                        degraded_mode=True,
                        error_reason=err_msg,
                        run_id=request.run_id,
                        application_id=request.application_id,
                        executed_at=now,
                    )
                raise LLMBudgetExceededError(err_msg)

            # Daily Cost Budget & AD-009 Policy Check
            if self.config.daily_cost_budget_usd is not None:
                known_cost, unknown_count = self.ledger.get_daily_cost_usd(today)

                # AD-009: Block if unpriced calls have already occurred today
                if unknown_count > 0:
                    err_msg = (
                        f"Daily LLM cost budget enforcement blocked: unpriced call recorded on {today} "
                        f"with active cost budget (${self.config.daily_cost_budget_usd:.4f}) (fail-closed per AD-009)."
                    )
                    logger.warning(err_msg)
                    self.ledger.record_call(
                        LLMCallRecord(
                            run_id=request.run_id,
                            application_id=request.application_id,
                            task=request.task,
                            model=model,
                            tokens={"input": None, "output": None, "total": None},
                            cost_usd=None,
                            cost_provenance="unknown",
                            latency_ms=0,
                            cache_hit=False,
                            outcome="BUDGET_EXCEEDED",
                            created_at=now,
                        )
                    )
                    if allow_degraded:
                        return LLMResponse(
                            content="",
                            model=model,
                            task=request.task,
                            latency_ms=0,
                            cache_hit=False,
                            degraded_mode=True,
                            error_reason=err_msg,
                            run_id=request.run_id,
                            application_id=request.application_id,
                            executed_at=now,
                        )
                    raise LLMBudgetExceededError(err_msg)

                # Check known cost spending ceiling
                if known_cost >= self.config.daily_cost_budget_usd:
                    err_msg = (
                        f"Daily LLM cost budget exhausted: ${known_cost:.4f}/${self.config.daily_cost_budget_usd:.4f} "
                        f"on {today}"
                    )
                    logger.warning(err_msg)
                    self.ledger.record_call(
                        LLMCallRecord(
                            run_id=request.run_id,
                            application_id=request.application_id,
                            task=request.task,
                            model=model,
                            tokens={"input": None, "output": None, "total": None},
                            cost_usd=None,
                            cost_provenance="unknown",
                            latency_ms=0,
                            cache_hit=False,
                            outcome="BUDGET_EXCEEDED",
                            created_at=now,
                        )
                    )
                    if allow_degraded:
                        return LLMResponse(
                            content="",
                            model=model,
                            task=request.task,
                            latency_ms=0,
                            cache_hit=False,
                            degraded_mode=True,
                            error_reason=err_msg,
                            run_id=request.run_id,
                            application_id=request.application_id,
                            executed_at=now,
                        )
                    raise LLMBudgetExceededError(err_msg)

                # AD-009: Require valid configured pricing before dispatching
                if not self._has_valid_pricing(model):
                    err_msg = (
                        f"Daily cost budget is active (${self.config.daily_cost_budget_usd:.4f}) but model '{model}' "
                        f"has no valid pricing configured in model_pricing (fail-closed per AD-009)."
                    )
                    logger.warning(err_msg)
                    self.ledger.record_call(
                        LLMCallRecord(
                            run_id=request.run_id,
                            application_id=request.application_id,
                            task=request.task,
                            model=model,
                            tokens={"input": None, "output": None, "total": None},
                            cost_usd=None,
                            cost_provenance="unknown",
                            latency_ms=0,
                            cache_hit=False,
                            outcome="BUDGET_EXCEEDED",
                            created_at=now,
                        )
                    )
                    if allow_degraded:
                        return LLMResponse(
                            content="",
                            model=model,
                            task=request.task,
                            latency_ms=0,
                            cache_hit=False,
                            degraded_mode=True,
                            error_reason=err_msg,
                            run_id=request.run_id,
                            application_id=request.application_id,
                            executed_at=now,
                        )
                    raise LLMBudgetExceededError(err_msg)

            # Circuit Breaker Check (Architecture Paragraph 545)
            if not self.circuit_breaker.can_execute():
                err_msg = (
                    f"LLM Circuit Breaker is OPEN for provider requests (state: {self.circuit_breaker.state})."
                )
                logger.warning(err_msg)
                self.ledger.record_call(
                    LLMCallRecord(
                        run_id=request.run_id,
                        application_id=request.application_id,
                        task=request.task,
                        model=model,
                        tokens={"input": None, "output": None, "total": None},
                        cost_usd=None,
                        cost_provenance="unknown",
                        latency_ms=0,
                        cache_hit=False,
                        outcome="CIRCUIT_OPEN",
                        created_at=now,
                    )
                )
                if allow_degraded:
                    return LLMResponse(
                        content="",
                        model=model,
                        task=request.task,
                        latency_ms=0,
                        cache_hit=False,
                        degraded_mode=True,
                        error_reason=err_msg,
                        run_id=request.run_id,
                        application_id=request.application_id,
                        executed_at=now,
                    )
                raise LLMCircuitBreakerOpenError(err_msg)

            # Dispatch External Completion
            start_time = time.perf_counter()
            try:
                content, tokens, cost_usd, cost_provenance, pricing_source = await self.client.complete(
                    model=model,
                    messages=request.messages,
                    timeout_seconds=request.timeout_seconds,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature,
                )
                latency_ms = int((time.perf_counter() - start_time) * 1000)

                # Record circuit breaker success
                self.circuit_breaker.record_success()

                response = LLMResponse(
                    content=content,
                    model=model,
                    task=request.task,
                    tokens=tokens,
                    cost_usd=cost_usd,
                    cost_provenance=cost_provenance,
                    pricing_source=pricing_source,
                    latency_ms=latency_ms,
                    cache_hit=False,
                    run_id=request.run_id,
                    application_id=request.application_id,
                    executed_at=now,
                    degraded_mode=False,
                )

                # Store in cache if eligible
                if request.cache_eligible and self.cache is not None:
                    cache_key = compute_cache_key(
                        task=request.task,
                        model=model,
                        messages=request.messages,
                        profile_version=request.profile_version,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        cache_scope=request.cache_scope,
                    )
                    self.cache.set(
                        key=cache_key,
                        response=response,
                        ttl_seconds=self.config.cache_ttl_seconds,
                        now=now,
                    )

                # Record call in ledger
                self.ledger.record_call(
                    LLMCallRecord(
                        run_id=request.run_id,
                        application_id=request.application_id,
                        task=request.task,
                        model=model,
                        tokens={
                            "input": tokens.input_tokens,
                            "output": tokens.output_tokens,
                            "total": tokens.total_tokens,
                        },
                        cost_usd=cost_usd,
                        cost_provenance=cost_provenance,
                        latency_ms=latency_ms,
                        cache_hit=False,
                        outcome="SUCCESS",
                        created_at=now,
                    )
                )

                return response

            except (LLMTimeoutError, LLMProviderError) as exc:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                self.circuit_breaker.record_failure(is_provider_error=True)
                self.ledger.record_call(
                    LLMCallRecord(
                        run_id=request.run_id,
                        application_id=request.application_id,
                        task=request.task,
                        model=model,
                        tokens={"input": None, "output": None, "total": None},
                        cost_usd=None,
                        cost_provenance="unknown",
                        latency_ms=latency_ms,
                        cache_hit=False,
                        outcome="TIMEOUT" if isinstance(exc, LLMTimeoutError) else "PROVIDER_ERROR",
                        created_at=now,
                    )
                )
                if allow_degraded:
                    logger.warning("LLM request failed; returning degraded response: %s", exc)
                    return LLMResponse(
                        content="",
                        model=model,
                        task=request.task,
                        latency_ms=latency_ms,
                        cache_hit=False,
                        degraded_mode=True,
                        error_reason=str(exc),
                        run_id=request.run_id,
                        application_id=request.application_id,
                        executed_at=now,
                    )
                raise

            except (LLMAuthenticationError, LLMMalformedResponseError) as exc:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                self.circuit_breaker.record_failure(is_provider_error=False)
                self.ledger.record_call(
                    LLMCallRecord(
                        run_id=request.run_id,
                        application_id=request.application_id,
                        task=request.task,
                        model=model,
                        tokens={"input": None, "output": None, "total": None},
                        cost_usd=None,
                        cost_provenance="unknown",
                        latency_ms=latency_ms,
                        cache_hit=False,
                        outcome="ERROR",
                        created_at=now,
                    )
                )
                if allow_degraded:
                    logger.warning("LLM request failed; returning degraded response: %s", exc)
                    return LLMResponse(
                        content="",
                        model=model,
                        task=request.task,
                        latency_ms=latency_ms,
                        cache_hit=False,
                        degraded_mode=True,
                        error_reason=str(exc),
                        run_id=request.run_id,
                        application_id=request.application_id,
                        executed_at=now,
                    )
                raise

            except BaseException:
                # Release in-flight probe on cancellation or unhandled system exceptions
                self.circuit_breaker.release_probe()
                raise


# ==============================================================================
# 8. Managed Singleton Accessor
# ==============================================================================

_managed_gateway_instance: Optional[LLMGateway] = None
_gateway_instance_lock = threading.Lock()


def get_managed_llm_gateway(
    client: Optional[OpenRouterClient] = None,
    config: Optional[LLMConfig] = None,
    ledger: Optional[LLMCallLedger] = None,
    cache: Optional[LLMCache] = None,
    reset: bool = False,
) -> LLMGateway:
    """Get or initialize the process-wide managed LLM Gateway singleton."""
    global _managed_gateway_instance
    with _gateway_instance_lock:
        if reset:
            _managed_gateway_instance = None
        if _managed_gateway_instance is None:
            from services.api.config import get_settings

            settings = get_settings()
            client = client or OpenRouterClient(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                app_name=settings.openrouter_app_name,
                site_url=settings.openrouter_site_url,
                pricing_table=settings.llm.model_pricing,
            )
            ledger = ledger or FileLLMCallLedger(Path("worker/sessions/llm_calls.jsonl"))
            cache = cache or FileLLMCache(Path("worker/sessions/llm_cache.json"))
            _managed_gateway_instance = LLMGateway(
                client=client,
                config=config or settings.llm,
                ledger=ledger,
                cache=cache,
            )
        return _managed_gateway_instance
