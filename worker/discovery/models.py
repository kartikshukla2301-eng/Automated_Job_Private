"""Canonical Job and Discovery models aligning with Architecture v1.0 LOCKED.

Following Section 10 and Section 14 (Data Model) of the locked architecture:
- Strongly typed Job representation.
- Preserves all database schema constraints from migrations/001_initial_schema.sql.
- Never invent missing job information.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JobStatus(str, Enum):
    """Job status aligning with ck_jobs_status in migrations/001_initial_schema.sql."""

    DISCOVERED = "DISCOVERED"
    MATCHED = "MATCHED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    IGNORED = "IGNORED"
    DUPLICATE = "DUPLICATE"


class SalaryInfo(BaseModel):
    """Explicitly available salary compensation details (never invented)."""

    model_config = ConfigDict(extra="forbid")

    min_amount: Optional[float] = Field(default=None, description="Minimum compensation if stated")
    max_amount: Optional[float] = Field(default=None, description="Maximum compensation if stated")
    currency: Optional[str] = Field(default=None, description="ISO currency code (e.g. USD, EUR, INR)")
    interval: Optional[str] = Field(
        default=None,
        description="Payment interval (e.g. year, month, hour)",
    )


class Job(BaseModel):
    """Canonical normalized Job model.

    Aligns with `jobs` table schema in migrations/001_initial_schema.sql and
    Architecture v1.0 LOCKED Section 10 & Section 14.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4, description="Primary key UUID")
    platform: str = Field(..., min_length=1, max_length=50, description="Platform (e.g. greenhouse, lever)")
    external_id: str = Field(..., min_length=1, max_length=255, description="Provider's unique job identifier")
    canonical_key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Key 2 deduplication string (normalized_company:normalized_title:location_bucket)",
    )
    company: str = Field(..., min_length=1, max_length=255, description="Display company name")
    normalized_company: str = Field(..., min_length=1, max_length=255, description="Normalized company name")
    title: str = Field(..., min_length=1, max_length=255, description="Job title")
    normalized_title: str = Field(..., min_length=1, max_length=255, description="Normalized job title")
    url: str = Field(..., min_length=1, description="Canonical job posting URL")
    description: Optional[str] = Field(default=None, description="Clean sanitized plain text job description")
    description_html: Optional[str] = Field(default=None, description="Original raw HTML description if provided")
    location: Optional[str] = Field(default=None, description="Raw location string (e.g. 'San Francisco, CA')")
    location_bucket: Optional[str] = Field(
        default=None,
        description="Normalized location classification (remote, hybrid, onsite, or normalized region)",
    )
    employment_type: Optional[str] = Field(
        default=None,
        description="Employment type if explicitly stated (e.g. Full-time, Contract, Internship)",
    )
    experience_requirements: Optional[str] = Field(
        default=None,
        description="Explicit experience requirements if stated (never invented)",
    )
    salary: Optional[SalaryInfo] = Field(
        default=None,
        description="Explicit salary information if stated (never invented)",
    )
    posted_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the job was posted by the employer (if provided)",
    )
    first_seen_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when our system first discovered this listing",
    )
    content_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        description="SHA-256 hash of normalized job description",
    )
    embedding: Optional[List[float]] = Field(default=None, description="Optional vector embedding representation")
    score: Optional[float] = Field(default=None, description="Overall matching score (0.00-100.00)")
    score_breakdown: Dict[str, Any] = Field(default_factory=dict, description="Component-level score breakdown")
    status: JobStatus = Field(default=JobStatus.DISCOVERED, description="Application lifecycle status")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw provider metadata, departments, offices, etc.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record update timestamp",
    )

    @field_validator("platform", "external_id", "company", "title")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Field cannot be empty or whitespace.")
        return clean


class DiscoverySummary(BaseModel):
    """Structured report returned upon completing a job discovery run."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(..., description="Provider name (e.g. greenhouse, lever)")
    company: str = Field(..., description="Target company or board identifier")
    total_discovered: int = Field(default=0, ge=0, description="Total raw job postings retrieved")
    new_jobs: int = Field(default=0, ge=0, description="Count of newly ingested jobs")
    updated_jobs: int = Field(default=0, ge=0, description="Count of existing jobs with modified descriptions")
    duplicate_jobs: int = Field(default=0, ge=0, description="Count of duplicate or unchanged jobs")
    rejected_records: int = Field(default=0, ge=0, description="Count of malformed or invalid job listings skipped")
    errors: List[str] = Field(default_factory=list, description="Diagnostic error messages encountered")
