"""DevLeveler canonical profile source with ETag caching and local file fallback (Phase 1.9).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 6, 8, 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from pydantic import ValidationError

from worker.profile.exceptions import (
    DevLevelerAuthError,
    DevLevelerConnectionError,
    ProfileParseError,
    ProfileValidationError,
)
from worker.profile.localfile import LocalFileProfileSource
from worker.profile.models import ProfileSnapshot
from worker.profile.source import ProfileSource

logger = logging.getLogger("worker.profile.devleveler")


class DevLevelerProfileSource(ProfileSource):
    """DevLeveler remote profile source implementing ETag caching and local fallback."""

    def __init__(
        self,
        base_url: str = "https://api.devleveler.com",
        api_token: Optional[str] = None,
        cache_path: Path = Path("worker/profile/cache/devleveler_profile.json"),
        fallback_source: Optional[ProfileSource] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.cache_path = cache_path
        self.fallback_source = fallback_source or LocalFileProfileSource(file_path=Path("fixtures/profile.yaml"))
        self._client = client

    def _read_cache(self) -> Optional[Dict[str, Any]]:
        """Read cached profile payload and ETag metadata if available."""
        if not self.cache_path.exists():
            return None
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception as err:
            logger.warning("Could not read DevLeveler profile cache: %s", err)
            return None

    def _write_cache(self, etag: Optional[str], profile_data: Dict[str, Any]) -> None:
        """Persist profile snapshot and ETag metadata to local cache."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_payload = {
                "etag": etag,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "profile": profile_data,
            }
            self.cache_path.write_text(json.dumps(cache_payload, indent=2), encoding="utf-8")
        except Exception as err:
            logger.warning("Could not write DevLeveler profile cache: %s", err)

    def check_staleness(self) -> bool:
        """Return True if cached profile is older than 24 hours."""
        cache_meta = self._read_cache()
        if not cache_meta or "cached_at" not in cache_meta:
            return True
        try:
            cached_at = datetime.fromisoformat(cache_meta["cached_at"])
            age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600.0
            return age_hours > 24.0
        except Exception:
            return True

    async def get_snapshot(self) -> ProfileSnapshot:
        """Retrieve candidate profile from DevLeveler, cache, or fallback source."""
        # 1. If no API token provided, log warning and use fallback source
        if not self.api_token:
            logger.info("DevLeveler API token not configured; utilizing local profile fallback source.")
            return await self.fallback_source.get_snapshot()

        cached_meta = self._read_cache()
        cached_etag = cached_meta.get("etag") if cached_meta else None

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
        if cached_etag:
            headers["If-None-Match"] = cached_etag

        endpoint = f"{self.base_url}/api/v1/me/job-agent-profile"

        try:
            client_ctx = self._client if self._client is not None else httpx.AsyncClient(timeout=10.0)
            async with client_ctx as client:
                response = await client.get(endpoint, headers=headers)

                # 2. 304 Not Modified -> return cached snapshot
                if response.status_code == 304 and cached_meta and "profile" in cached_meta:
                    logger.info("DevLeveler profile not modified (ETag %s). Using cached snapshot.", cached_etag)
                    return ProfileSnapshot(**cached_meta["profile"])

                # 3. 200 OK -> parse payload, update cache, return
                if response.status_code == 200:
                    data = response.json()
                    new_etag = response.headers.get("ETag") or response.headers.get("etag")
                    self._write_cache(new_etag, data)
                    return ProfileSnapshot(**data)

                # 4. 401 / 403 Unauthorized
                if response.status_code in (401, 403):
                    msg = f"DevLeveler authentication failed with HTTP {response.status_code}"
                    logger.error(msg)
                    raise DevLevelerAuthError(msg)

                # 5. Other HTTP status codes (5xx, 4xx)
                logger.warning("DevLeveler returned unexpected status HTTP %s", response.status_code)

        except (httpx.RequestError, httpx.TimeoutException) as net_err:
            logger.warning("DevLeveler network failure: %s", net_err)
        except ValidationError as val_err:
            logger.error("DevLeveler profile validation failure: %s", val_err)
            raise ProfileValidationError(f"Invalid profile schema from DevLeveler: {val_err}") from val_err

        # Fallback to local cache if available
        if cached_meta and "profile" in cached_meta:
            logger.info("Recovering from cache following DevLeveler unreachable status.")
            return ProfileSnapshot(**cached_meta["profile"])

        # Fallback to LocalFileProfileSource
        if self.fallback_source is not None:
            logger.info("Falling back to local file profile source.")
            return await self.fallback_source.get_snapshot()

        raise DevLevelerConnectionError(f"Could not connect to DevLeveler endpoint: {endpoint}")
