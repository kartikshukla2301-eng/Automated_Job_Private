"""Local Small-Model (Ollama) Last-Resort LLM Fallback (Phase 4.3, OI-7).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Part I.4, Optional Improvement OI-7:
  "Local small model (for example via Ollama) as a last-resort LLM fallback when free
  quotas are exhausted.")
- docs/BUILD_RULES.md ("All runtime LLM calls go through one LLM Gateway; no scattered
  direct OpenRouter calls." and "Never invent candidate facts or token/cost counts.")

DESIGN NOTE (why this is a separate, additive module rather than an edit to
`worker/core/llm_gateway.py`):
`LLMGateway.execute()` is the locked central routing/budget/circuit-breaker/cache
pipeline (AGENTS.md: "Never silently change ... model routing ... safety gates").
This module does not modify that method at all. Instead it wraps it: it calls the
existing `LLMGateway.execute()` exactly as before, and only when that call already
decided to return a degraded (empty-content) response — because the daily budget is
exhausted, the circuit breaker is open, or the provider errored/timed out — does it
attempt one local, zero-cost completion as a last resort. If the local attempt is not
configured or itself fails, the original degraded response is returned unchanged, so
callers that do not opt into this wrapper see byte-for-byte the same gateway behavior
as before.

All usage/cost accounting still goes through the same `LLMCallLedger` used by
`LLMGateway`, so local-fallback calls remain fully auditable. Local inference has no
metered API cost, so `cost_usd=0.0` with `cost_provenance="reported"` is an honest,
non-fabricated value (never defaulted to 0.0 for an *unknown*-cost case, only for this
genuinely free, local case).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from worker.core.exceptions import (
    LLMMalformedResponseError,
    LLMProviderError,
    LLMTimeoutError,
)
from worker.core.llm_gateway import (
    CostProvenance,
    LLMCallRecord,
    LLMGateway,
    LLMRequest,
    LLMResponse,
    LLMTokenUsage,
)

logger = logging.getLogger("worker.core.local_llm_fallback")

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"


class LocalOllamaClient:
    """Thin async client for a locally running Ollama server's chat completion API.

    Never called directly by feature code and never a substitute for the central
    gateway's routing: it is only invoked through `execute_with_local_fallback()`
    below, after the gateway itself has already decided the primary path is
    unavailable. No API key, no outbound network call beyond localhost.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._external_client = http_client
        self._client: Optional[httpx.AsyncClient] = http_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()
        return self._client

    async def aclose(self) -> None:
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
        """Dispatch a chat completion to the local Ollama server.

        Returns the same `(content, tokens, cost_usd, cost_provenance, pricing_source)`
        tuple shape as `OpenRouterClient.complete()` so both can be driven uniformly.
        """
        client = await self._get_client()
        url = f"{self.base_url}/api/chat"

        options: Dict[str, Any] = {"temperature": temperature}
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": options,
        }

        try:
            response = await client.post(url, json=payload, timeout=timeout_seconds)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Local Ollama request timed out after {timeout_seconds}s: {exc}") from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Local Ollama transport error (is `ollama serve` running at {self.base_url}?): {exc}"
            ) from exc

        if response.status_code == 404:
            raise LLMProviderError(
                f"Local Ollama model '{model}' not found. Pull it first with `ollama pull {model}`."
            )
        if response.status_code >= 500:
            raise LLMProviderError(f"Local Ollama server error (HTTP {response.status_code}): {response.text}")
        if response.status_code != 200:
            raise LLMProviderError(f"Local Ollama unexpected HTTP {response.status_code}: {response.text}")

        try:
            data = response.json()
        except Exception as exc:
            raise LLMMalformedResponseError(f"Local Ollama returned non-JSON payload: {exc}") from exc

        message = data.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise LLMMalformedResponseError("Local Ollama response missing 'message.content'.")

        content = message["content"]
        if not isinstance(content, str):
            raise LLMMalformedResponseError("Local Ollama 'message.content' was not a string.")

        tokens = LLMTokenUsage()
        prompt_count = data.get("prompt_eval_count")
        eval_count = data.get("eval_count")
        if isinstance(prompt_count, int) and not isinstance(prompt_count, bool) and prompt_count >= 0:
            tokens.input_tokens = prompt_count
        if isinstance(eval_count, int) and not isinstance(eval_count, bool) and eval_count >= 0:
            tokens.output_tokens = eval_count
        if tokens.input_tokens is not None and tokens.output_tokens is not None:
            tokens.total_tokens = tokens.input_tokens + tokens.output_tokens

        # Local inference has no metered API cost: $0.00 is a true reported value here,
        # never a fabricated stand-in for an unknown remote cost.
        return content, tokens, 0.0, "reported", "local_ollama_zero_cost"


async def execute_with_local_fallback(
    gateway: LLMGateway,
    request: LLMRequest,
    local_client: Optional[LocalOllamaClient],
    local_model: str = DEFAULT_OLLAMA_MODEL,
) -> LLMResponse:
    """Execute through the central `LLMGateway` with an optional local last-resort fallback.

    Behaviour:
    1. Always calls `gateway.execute(request, allow_degraded=True)` first, unchanged.
    2. If that response is not degraded (success or cache hit), it is returned as-is.
    3. If it IS degraded (daily budget exhausted, circuit breaker open, provider error/
       timeout) and a `local_client` is configured, attempt exactly one local
       completion as a last resort.
    4. If the local attempt also fails, or no `local_client` was configured, the
       original degraded response from step 1 is returned unchanged — callers always
       get a valid `LLMResponse`, never a different error surface than before.

    The local fallback never bypasses the gateway: step 1 still runs the full budget,
    circuit-breaker, and cache checks exactly as locked; this function only adds a
    fallback *after* the gateway has already decided the primary path is unavailable.
    """
    primary_response = await gateway.execute(request, allow_degraded=True)

    if not primary_response.degraded_mode or local_client is None:
        return primary_response

    start_time = time.perf_counter()
    try:
        content, tokens, cost_usd, cost_provenance, pricing_source = await local_client.complete(
            model=local_model,
            messages=request.messages,
            timeout_seconds=request.timeout_seconds,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
    except Exception as exc:
        logger.warning(
            "Local Ollama fallback unavailable after primary degraded (%s); "
            "returning the original degraded response.",
            exc,
        )
        return primary_response

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    now = datetime.now(timezone.utc)
    fallback_response = LLMResponse(
        content=content,
        model=f"local:{local_model}",
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
        error_reason=(
            f"Primary LLM path degraded ({primary_response.error_reason}); "
            f"served by local Ollama fallback model '{local_model}'."
        ),
    )

    gateway.ledger.record_call(
        LLMCallRecord(
            run_id=request.run_id,
            application_id=request.application_id,
            task=request.task,
            model=fallback_response.model,
            tokens={
                "input": tokens.input_tokens,
                "output": tokens.output_tokens,
                "total": tokens.total_tokens,
            },
            cost_usd=cost_usd,
            cost_provenance=cost_provenance,
            latency_ms=latency_ms,
            cache_hit=False,
            outcome="LOCAL_FALLBACK_SUCCESS",
            created_at=now,
        )
    )

    logger.info(
        "Local Ollama fallback served task '%s' after primary degraded (model=%s, latency_ms=%d)",
        request.task,
        local_model,
        latency_ms,
    )
    return fallback_response
