"""Greenhouse public job board discovery adapter.

Fetches and normalizes listings from Greenhouse's public API:
GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true

Follows Architecture v1.0 LOCKED and Phase 1.1 Requirements:
- Provider-specific isolation.
- Normalizes into canonical Job model.
- Explicit error handling for 404, 429, 5xx, timeouts, and malformed payloads.
- Strictly bounds network requests to approved Greenhouse endpoints.
- Never fabricates missing job data.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import httpx

from worker.discovery.models import Job, JobStatus, SalaryInfo
from worker.discovery.normalization import (
    compute_canonical_key,
    compute_content_hash,
    normalize_company,
    normalize_location,
    normalize_title,
    normalize_url,
)
from worker.discovery.security import is_safe_discovery_url, sanitize_job_description
from worker.providers.base import JobDiscoveryAdapter
from worker.providers.exceptions import (
    ProviderDataError,
    ProviderNetworkError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    UnsafeUrlError,
)

logger = logging.getLogger("worker.providers.greenhouse_discovery")

DEFAULT_GREENHOUSE_HOST = "boards-api.greenhouse.io"
DEFAULT_TIMEOUT_SECONDS = 15.0


class GreenhouseDiscoveryAdapter(JobDiscoveryAdapter):
    """Discovery adapter for Greenhouse public job boards."""

    name: str = "greenhouse"

    def __init__(
        self,
        base_host: str = DEFAULT_GREENHOUSE_HOST,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_host = base_host
        self.timeout = timeout

    def build_board_url(self, board_token: str) -> str:
        """Construct the canonical public jobs API URL for a board."""
        clean_token = board_token.strip().lower()
        if not clean_token:
            raise ValueError("Greenhouse board_token cannot be empty.")
        return f"https://{self.base_host}/v1/boards/{clean_token}/jobs?content=true"

    def normalize_job_record(
        self,
        raw_job: Dict[str, Any],
        board_token: str,
        company_name: Optional[str] = None,
    ) -> Optional[Job]:
        """Normalize a single raw Greenhouse job JSON dictionary into a canonical Job model.

        Returns None if the record is missing required fields (e.g. id or title).
        """
        raw_id = raw_job.get("id")
        raw_title = raw_job.get("title")

        if raw_id is None or not str(raw_id).strip():
            logger.warning("Skipping Greenhouse job record missing id: %s", raw_job)
            return None

        if not raw_title or not str(raw_title).strip():
            logger.warning("Skipping Greenhouse job record missing title: id=%s", raw_id)
            return None

        external_id = str(raw_id).strip()
        title = str(raw_title).strip()
        company = (company_name or board_token).strip()

        norm_company = normalize_company(company)
        norm_title = normalize_title(title)

        # Location extraction
        raw_location: Optional[str] = None
        loc_data = raw_job.get("location")
        if isinstance(loc_data, dict):
            raw_location = loc_data.get("name")
        elif isinstance(loc_data, str):
            raw_location = loc_data

        clean_location, location_bucket = normalize_location(raw_location)
        canonical_key = compute_canonical_key(company, title, location_bucket)

        # Canonical URL
        raw_url = raw_job.get("absolute_url") or f"https://boards.greenhouse.io/{board_token}/jobs/{external_id}"
        canonical_url = normalize_url(str(raw_url))

        # Description and content hash
        content_html = raw_job.get("content")
        sanitized_description = sanitize_job_description(content_html)
        content_hash = compute_content_hash(sanitized_description, fallback_title=title)

        # Posted timestamp (Greenhouse provides 'updated_at' in ISO format)
        posted_at: Optional[datetime] = None
        raw_updated_at = raw_job.get("updated_at")
        if raw_updated_at and isinstance(raw_updated_at, str):
            try:
                posted_at = datetime.fromisoformat(raw_updated_at.replace("Z", "+00:00"))
            except ValueError:
                posted_at = None

        # Metadata parsing for employment type
        employment_type: Optional[str] = None
        salary: Optional[SalaryInfo] = None
        metadata = raw_job.get("metadata") or []
        if isinstance(metadata, list):
            for meta_item in metadata:
                if isinstance(meta_item, dict):
                    meta_name = (meta_item.get("name") or "").lower()
                    meta_val = meta_item.get("value")
                    if meta_val and any(k in meta_name for k in ("employment type", "job type", "commitment")):
                        employment_type = str(meta_val).strip()
                    elif meta_val and "salary" in meta_name:
                        # Only set if structured or numeric data is parsed, never invent
                        try:
                            val_float = float(meta_val)
                            salary = SalaryInfo(min_amount=val_float, max_amount=val_float)
                        except (ValueError, TypeError):
                            pass

        return Job(
            platform=self.name,
            external_id=external_id,
            canonical_key=canonical_key,
            company=company,
            normalized_company=norm_company,
            title=title,
            normalized_title=norm_title,
            url=canonical_url,
            description=sanitized_description if sanitized_description else None,
            description_html=str(content_html) if content_html else None,
            location=clean_location,
            location_bucket=location_bucket,
            employment_type=employment_type,
            experience_requirements=None,  # Never invent
            salary=salary,
            posted_at=posted_at,
            first_seen_at=datetime.now(timezone.utc),
            content_hash=content_hash,
            status=JobStatus.DISCOVERED,
            metadata={
                "departments": raw_job.get("departments", []),
                "offices": raw_job.get("offices", []),
                "requisition_id": raw_job.get("requisition_id"),
                "internal_job_id": raw_job.get("internal_job_id"),
            },
        )

    async def fetch_jobs(
        self,
        company: str,
        client: Optional[httpx.AsyncClient] = None,
        company_name: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Job]:
        """Fetch and normalize all public jobs from a Greenhouse board."""
        board_token = company.strip().lower()
        url = self.build_board_url(board_token)

        if not is_safe_discovery_url(url):
            raise UnsafeUrlError(f"Rejected unsafe Greenhouse discovery URL: {url}")

        headers = {
            "User-Agent": "JobAgent-Discovery/1.0 (+https://github.com/kartikshukla2301-eng/Automated_Job_Private)",
            "Accept": "application/json",
        }

        should_close_client = False
        active_client = client
        if active_client is None:
            active_client = httpx.AsyncClient(timeout=self.timeout)
            should_close_client = True

        try:
            response = await active_client.get(url, headers=headers)

            if response.status_code == 404:
                raise ProviderNotFoundError(f"Greenhouse board '{board_token}' was not found (HTTP 404).")
            if response.status_code == 429:
                raise ProviderRateLimitError(f"Greenhouse rate limit exceeded for board '{board_token}' (HTTP 429).")
            if response.status_code >= 500:
                raise ProviderNetworkError(
                    f"Greenhouse service error (HTTP {response.status_code}) while fetching board '{board_token}'."
                )
            if response.status_code != 200:
                raise ProviderNetworkError(
                    f"Greenhouse unexpected status HTTP {response.status_code} for board '{board_token}'."
                )

            try:
                data = response.json()
            except Exception as exc:
                raise ProviderDataError(f"Failed to parse Greenhouse JSON response: {exc}") from exc

            raw_jobs = data.get("jobs")
            if not isinstance(raw_jobs, list):
                raise ProviderDataError("Malformed Greenhouse response: 'jobs' field is not a list.")

            normalized_jobs: List[Job] = []
            for item in raw_jobs:
                if isinstance(item, dict):
                    job = self.normalize_job_record(item, board_token, company_name=company_name)
                    if job is not None:
                        normalized_jobs.append(job)

            return normalized_jobs

        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ProviderTimeoutError(
                f"Timed out fetching Greenhouse board '{board_token}': {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderNetworkError(
                f"Network connection failure fetching Greenhouse board '{board_token}': {exc}"
            ) from exc
        finally:
            if should_close_client:
                await active_client.aclose()
