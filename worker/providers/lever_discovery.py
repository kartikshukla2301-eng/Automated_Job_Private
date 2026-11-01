"""Lever public postings discovery adapter.

Fetches and normalizes listings from Lever's public API:
GET https://api.lever.co/v0/postings/{company}?mode=json&limit=100&skip=0

Follows Architecture v1.0 LOCKED and Phase 1.1 Requirements:
- Provider-specific isolation.
- Supports pagination via limit and skip.
- Normalizes into canonical Job model.
- Explicit error handling for 404, 429, 5xx, timeouts, and malformed payloads.
- Strictly bounds network requests to approved Lever endpoints.
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

logger = logging.getLogger("worker.providers.lever_discovery")

DEFAULT_LEVER_HOST = "api.lever.co"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_PAGE_SIZE = 100
MAX_PAGINATION_PAGES = 50


class LeverDiscoveryAdapter(JobDiscoveryAdapter):
    """Discovery adapter for Lever public job postings."""

    name: str = "lever"

    def __init__(
        self,
        base_host: str = DEFAULT_LEVER_HOST,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        self.base_host = base_host
        self.timeout = timeout
        self.page_size = page_size

    def build_postings_url(self, company: str, limit: int, skip: int) -> str:
        """Construct public Lever postings API URL with pagination."""
        clean_company = company.strip().lower()
        if not clean_company:
            raise ValueError("Lever company identifier cannot be empty.")
        return f"https://{self.base_host}/v0/postings/{clean_company}?mode=json&limit={limit}&skip={skip}"

    def normalize_job_record(
        self,
        raw_job: Dict[str, Any],
        company_id: str,
        company_name: Optional[str] = None,
    ) -> Optional[Job]:
        """Normalize a single raw Lever posting dictionary into a canonical Job model.

        Returns None if the record is missing required fields (e.g. id or title/text).
        """
        raw_id = raw_job.get("id")
        raw_title = raw_job.get("text")

        if not raw_id or not str(raw_id).strip():
            logger.warning("Skipping Lever job record missing id: %s", raw_job)
            return None

        if not raw_title or not str(raw_title).strip():
            logger.warning("Skipping Lever job record missing title text: id=%s", raw_id)
            return None

        external_id = str(raw_id).strip()
        title = str(raw_title).strip()
        company = (company_name or company_id).strip()

        norm_company = normalize_company(company)
        norm_title = normalize_title(title)

        categories = raw_job.get("categories") or {}
        raw_location = categories.get("location") if isinstance(categories, dict) else None
        clean_location, location_bucket = normalize_location(raw_location)

        # Lever workplaceType: remote, hybrid, onsite
        workplace_type = (raw_job.get("workplaceType") or "").strip().lower()
        if workplace_type in ("remote", "hybrid", "onsite"):
            location_bucket = workplace_type

        canonical_key = compute_canonical_key(company, title, location_bucket)

        # Canonical URL
        raw_url = raw_job.get("hostedUrl") or f"https://jobs.lever.co/{company_id}/{external_id}"
        canonical_url = normalize_url(str(raw_url))

        # Build description from HTML/text fragments
        desc_parts: List[str] = []
        if raw_job.get("description"):
            desc_parts.append(str(raw_job["description"]))
        elif raw_job.get("descriptionPlain"):
            desc_parts.append(str(raw_job["descriptionPlain"]))

        lists = raw_job.get("lists") or []
        if isinstance(lists, list):
            for item in lists:
                if isinstance(item, dict):
                    if item.get("text"):
                        desc_parts.append(f"<h3>{item['text']}</h3>")
                    if item.get("content"):
                        desc_parts.append(str(item["content"]))

        if raw_job.get("additional"):
            desc_parts.append(str(raw_job["additional"]))
        elif raw_job.get("additionalPlain"):
            desc_parts.append(str(raw_job["additionalPlain"]))

        full_raw_desc = "\n".join(desc_parts)
        sanitized_description = sanitize_job_description(full_raw_desc)
        content_hash = compute_content_hash(sanitized_description, fallback_title=title)

        # Posted timestamp (createdAt in epoch milliseconds)
        posted_at: Optional[datetime] = None
        created_at_ms = raw_job.get("createdAt")
        if created_at_ms and isinstance(created_at_ms, (int, float)):
            try:
                posted_at = datetime.fromtimestamp(created_at_ms / 1000.0, timezone.utc)
            except (ValueError, OSError):
                posted_at = None

        # Employment type from categories.commitment (e.g. 'Full-time')
        employment_type: Optional[str] = None
        if isinstance(categories, dict) and categories.get("commitment"):
            employment_type = str(categories["commitment"]).strip()

        # Structured salary information (never invented)
        salary: Optional[SalaryInfo] = None
        salary_range = raw_job.get("salaryRange")
        if isinstance(salary_range, dict):
            raw_min = salary_range.get("min")
            raw_max = salary_range.get("max")
            currency = salary_range.get("currency")
            interval_raw = salary_range.get("interval")

            interval: Optional[str] = None
            if interval_raw:
                int_str = str(interval_raw).lower()
                if "year" in int_str:
                    interval = "year"
                elif "month" in int_str:
                    interval = "month"
                elif "hour" in int_str:
                    interval = "hour"
                else:
                    interval = int_str

            min_val: Optional[float] = None
            max_val: Optional[float] = None
            try:
                if raw_min is not None:
                    min_val = float(raw_min)
                if raw_max is not None:
                    max_val = float(raw_max)
            except (ValueError, TypeError):
                pass

            if min_val is not None or max_val is not None:
                salary = SalaryInfo(
                    min_amount=min_val,
                    max_amount=max_val,
                    currency=str(currency) if currency else None,
                    interval=interval,
                )

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
            description_html=full_raw_desc if full_raw_desc else None,
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
                "department": categories.get("department") if isinstance(categories, dict) else None,
                "team": categories.get("team") if isinstance(categories, dict) else None,
                "allLocations": categories.get("allLocations") if isinstance(categories, dict) else [],
                "applyUrl": raw_job.get("applyUrl"),
                "workplaceType": raw_job.get("workplaceType"),
            },
        )

    async def fetch_jobs(
        self,
        company: str,
        client: Optional[httpx.AsyncClient] = None,
        company_name: Optional[str] = None,
        **kwargs: Any,
    ) -> List[Job]:
        """Fetch and normalize all public jobs from Lever, handling pagination."""
        company_id = company.strip().lower()

        headers = {
            "User-Agent": "JobAgent-Discovery/1.0 (+https://github.com/kartikshukla2301-eng/Automated_Job_Private)",
            "Accept": "application/json",
        }

        should_close_client = False
        active_client = client
        if active_client is None:
            active_client = httpx.AsyncClient(timeout=self.timeout)
            should_close_client = True

        all_jobs: List[Job] = []
        skip = 0
        limit = self.page_size
        page_count = 0

        try:
            while page_count < MAX_PAGINATION_PAGES:
                url = self.build_postings_url(company_id, limit=limit, skip=skip)

                if not is_safe_discovery_url(url):
                    raise UnsafeUrlError(f"Rejected unsafe Lever discovery URL: {url}")

                response = await active_client.get(url, headers=headers)

                if response.status_code == 404:
                    raise ProviderNotFoundError(f"Lever company postings for '{company_id}' not found (HTTP 404).")
                if response.status_code == 429:
                    raise ProviderRateLimitError(f"Lever rate limit exceeded for '{company_id}' (HTTP 429).")
                if response.status_code >= 500:
                    raise ProviderNetworkError(
                        f"Lever service error (HTTP {response.status_code}) for '{company_id}'."
                    )
                if response.status_code != 200:
                    raise ProviderNetworkError(
                        f"Lever unexpected status HTTP {response.status_code} for '{company_id}'."
                    )

                try:
                    data = response.json()
                except Exception as exc:
                    raise ProviderDataError(f"Failed to parse Lever JSON response: {exc}") from exc

                if not isinstance(data, list):
                    raise ProviderDataError("Malformed Lever response: root element is not a JSON list.")

                # If no records returned, we reached the end of listings
                if not data:
                    break

                for raw_item in data:
                    if isinstance(raw_item, dict):
                        job = self.normalize_job_record(raw_item, company_id, company_name=company_name)
                        if job is not None:
                            all_jobs.append(job)

                # If returned items are fewer than limit, this is the last page
                if len(data) < limit:
                    break

                skip += limit
                page_count += 1

            return all_jobs

        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ProviderTimeoutError(
                f"Timed out fetching Lever postings for '{company_id}': {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderNetworkError(
                f"Network connection failure fetching Lever postings for '{company_id}': {exc}"
            ) from exc
        finally:
            if should_close_client:
                await active_client.aclose()
