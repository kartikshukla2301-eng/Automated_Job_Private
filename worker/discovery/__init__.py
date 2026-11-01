"""Job Discovery, normalization, deduplication, and repository abstractions."""

from worker.discovery.models import DiscoverySummary, Job, JobStatus, SalaryInfo
from worker.discovery.normalization import (
    compute_canonical_key,
    compute_content_hash,
    normalize_company,
    normalize_location,
    normalize_title,
    normalize_url,
)
from worker.discovery.repository import InMemoryJobRepository, JobRepository
from worker.discovery.security import is_safe_discovery_url, sanitize_job_description
from worker.discovery.service import JobDiscoveryService

__all__ = [
    "DiscoverySummary",
    "InMemoryJobRepository",
    "Job",
    "JobDiscoveryService",
    "JobRepository",
    "JobStatus",
    "SalaryInfo",
    "compute_canonical_key",
    "compute_content_hash",
    "is_safe_discovery_url",
    "normalize_company",
    "normalize_location",
    "normalize_title",
    "normalize_url",
    "sanitize_job_description",
]
