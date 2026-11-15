"""In-memory sliding window rate limiter for API endpoints (Phase 2.3).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from collections import defaultdict
import threading
import time
from typing import Callable, Dict, List, Optional
from fastapi import HTTPException, Request, Response, status


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Storage: key -> list of request timestamps (epoch seconds)
        self._timestamps: Dict[str, List[float]] = defaultdict(list)

    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int, int]:
        """Check whether request is allowed within sliding window.

        Returns (is_allowed, remaining_requests, reset_seconds).
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            # Purge timestamps older than the window
            cleaned = [ts for ts in self._timestamps[key] if ts > window_start]
            self._timestamps[key] = cleaned

            current_count = len(cleaned)
            if current_count >= limit:
                # Oldest timestamp inside window determines reset time
                oldest = cleaned[0] if cleaned else now
                reset_seconds = max(1, int(oldest + window_seconds - now))
                return False, 0, reset_seconds

            # Allow request and append timestamp
            self._timestamps[key].append(now)
            remaining = max(0, limit - current_count - 1)
            reset_seconds = window_seconds
            return True, remaining, reset_seconds

    def reset_key(self, key: str) -> None:
        """Reset rate limiter state for a specific key (useful for tests)."""
        with self._lock:
            if key in self._timestamps:
                del self._timestamps[key]


# Global rate limiter instance
_global_limiter = SlidingWindowRateLimiter()


def rate_limit(requests_per_minute: int = 60) -> Callable:
    """FastAPI dependency factory enforcing rate limits with standard HTTP headers."""

    async def _rate_limiter_dependency(request: Request, response: Response) -> None:
        # Determine client key: User-ID or Client IP
        client_key = request.headers.get("X-User-ID") or (request.client.host if request.client else "unknown")
        action_key = f"{client_key}:{request.url.path}"

        allowed, remaining, reset_secs = _global_limiter.check_rate_limit(
            key=action_key,
            limit=requests_per_minute,
            window_seconds=60,
        )

        # Inject standard rate limit headers
        response.headers["X-RateLimit-Limit"] = str(requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_secs)

        if not allowed:
            response.headers["Retry-After"] = str(reset_secs)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: Maximum {requests_per_minute} requests per minute allowed.",
                headers={"Retry-After": str(reset_secs)},
            )

    return _rate_limiter_dependency
