"""Strongly typed Pydantic models for Candidate Profile snapshots."""

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EducationEntry(BaseModel):
    """Education history entry."""

    model_config = ConfigDict(extra="forbid")

    institution: str = Field(..., min_length=1, description="Name of school, college, or university")
    degree: Optional[str] = Field(default=None, description="Degree or certificate name (e.g. B.Tech, B.S.)")
    field_of_study: Optional[str] = Field(default=None, description="Major, discipline, or field of study")
    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM or YYYY)")
    end_date: Optional[str] = Field(default=None, description="End or expected graduation date (YYYY-MM or YYYY)")
    grade: Optional[str] = Field(default=None, description="GPA, percentage, or grade achieved")


class ExperienceEntry(BaseModel):
    """Work experience history entry."""

    model_config = ConfigDict(extra="forbid")

    company: str = Field(..., min_length=1, description="Company or organization name")
    title: str = Field(..., min_length=1, description="Job title or role")
    location: Optional[str] = Field(default=None, description="Job location (city, state, country, or Remote)")
    start_date: Optional[str] = Field(default=None, description="Start date (YYYY-MM or YYYY)")
    end_date: Optional[str] = Field(default=None, description="End date (YYYY-MM or YYYY), or None if current")
    is_current: bool = Field(default=False, description="Whether this is the candidate's current role")
    description: Optional[str] = Field(default=None, description="Role summary and responsibilities")
    highlights: List[str] = Field(default_factory=list, description="Key accomplishments or bullet points")


class SkillEntry(BaseModel):
    """Technical or professional skill entry with optional experience duration."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Skill name")
    years: Optional[float] = Field(default=None, ge=0.0, description="Years of experience with this skill")

    @model_validator(mode="before")
    @classmethod
    def parse_from_string_or_dict(cls, data: Any) -> Any:
        if isinstance(data, str):
            return {"name": data.strip()}
        return data


class ProjectEntry(BaseModel):
    """Project portfolio entry."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, description="Project title")
    description: Optional[str] = Field(default=None, description="Project summary and architecture details")
    technologies: List[str] = Field(default_factory=list, description="Technologies and frameworks utilized")
    link: Optional[str] = Field(default=None, description="Repository or live demonstration URL")


class CandidateDetails(BaseModel):
    """Canonical candidate identity, contact information, background, and links."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Candidate full name")
    email: str = Field(..., min_length=3, description="Contact email address")
    phone: Optional[str] = Field(default=None, description="Contact phone number")
    location: Optional[str] = Field(default=None, description="Current primary location")
    education: List[EducationEntry] = Field(default_factory=list, description="Education history")
    experience: List[ExperienceEntry] = Field(default_factory=list, description="Employment history")
    skills: List[SkillEntry] = Field(default_factory=list, description="Verified skills list")
    projects: List[ProjectEntry] = Field(default_factory=list, description="Featured projects")
    links: Dict[str, str] = Field(
        default_factory=dict,
        description="External profile URLs (e.g. github, linkedin, portfolio)",
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip()
        if not EMAIL_REGEX.match(clean):
            raise ValueError(f"Invalid email address format: '{clean}'")
        return clean


class CandidatePreferences(BaseModel):
    """Job search preferences."""

    model_config = ConfigDict(extra="forbid")

    roles: List[str] = Field(default_factory=list, description="Target job titles or role categories")
    locations: List[str] = Field(default_factory=list, description="Preferred work locations")
    work_modes: List[str] = Field(default_factory=list, description="Preferred work modes: remote, hybrid, onsite")
    levels: List[str] = Field(default_factory=list, description="Target seniority levels: intern, junior, mid, senior")


def compute_profile_version(payload: Dict[str, Any]) -> str:
    """Compute a deterministic SHA256 version hash for normalized candidate profile content."""
    # Extract only the structural content that defines the candidate's verified profile
    normalized = {
        "schema_version": payload.get("schema_version", 1),
        "candidate": payload.get("candidate", {}),
        "preferences": payload.get("preferences", {}),
    }
    canonical_json = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]


class ProfileSnapshot(BaseModel):
    """Complete versioned snapshot of candidate profile data consumed by the worker."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(default=1, description="Data contract schema version")
    profile_version: str = Field(..., min_length=1, description="Deterministic profile version or hash")
    synced_at: Optional[datetime] = Field(default=None, description="Timestamp when the snapshot was generated/synced")
    candidate: CandidateDetails = Field(..., description="Canonical candidate identity and background")
    preferences: CandidatePreferences = Field(
        default_factory=CandidatePreferences,
        description="Job search preferences",
    )
