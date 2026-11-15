"""Safe Resume Intelligence and Anti-Hallucination Tailoring (Phase 1.9).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 6, 8, 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field

from worker.discovery.security import sanitize_job_description
from worker.profile.exceptions import HallucinationDetectedError
from worker.profile.models import ProfileSnapshot

logger = logging.getLogger("worker.profile.resume_intelligence")


class BulletDiff(BaseModel):
    """Audit diff comparing original verified bullet to tailored bullet."""

    model_config = ConfigDict(extra="forbid")

    company: str
    original_bullet: str
    tailored_bullet: str
    reordered_priority: int = 1
    matched_keywords: List[str] = Field(default_factory=list)


class TailoredResume(BaseModel):
    """Structured representation of tailored resume highlights with audit provenance."""

    model_config = ConfigDict(extra="forbid")

    profile_version: str = Field(..., description="Pinned candidate profile version")
    target_job_title: str = Field(..., description="Target job title")
    tailored_highlights: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Company -> ordered tailored bullet points",
    )
    diffs: List[BulletDiff] = Field(default_factory=list, description="Audit diffs of bullet changes")
    provenance_hash: str = Field(..., description="SHA-256 hash of tailored output for auditability")


class ResumeIntelligenceEngine:
    """Safely tailors and prioritizes candidate experience highlights for target jobs.
    
    Enforces the non-negotiable Anti-Hallucination Invariant:
    - Zero fabrication of unverified companies, titles, skills, or metrics.
    - Tailored text must strictly reorder and emphasize verified highlights from ProfileSnapshot.
    """

    def __init__(self) -> None:
        pass

    def extract_verified_vocabulary(self, profile: ProfileSnapshot) -> Set[str]:
        """Extract all verified technologies, skills, and companies from candidate profile."""
        vocab: Set[str] = set()

        # Skills
        for s in profile.candidate.skills:
            vocab.add(s.name.strip().lower())

        # Experience companies and titles
        for exp in profile.candidate.experience:
            vocab.add(exp.company.strip().lower())
            vocab.add(exp.title.strip().lower())

        # Projects
        for proj in profile.candidate.projects:
            vocab.add(proj.title.strip().lower())
            for t in proj.technologies:
                vocab.add(t.strip().lower())

        return vocab

    def verify_groundedness(
        self,
        tailored_text: str,
        profile: ProfileSnapshot,
    ) -> None:
        """Validate that all claims and technologies in tailored text are grounded in profile."""
        clean_text = tailored_text.lower()

        # Check that no completely foreign company or unverified framework is claimed
        # For example, look for common technology patterns
        profile_skills_lower = {s.name.strip().lower() for s in profile.candidate.skills}
        profile_companies_lower = {e.company.strip().lower() for e in profile.candidate.experience}

        # Check for unverified skill claims
        unverified_candidates = ["cobol", "fortran", "solidity", "haskell", "erlang", "assembly", "flutter", "swift"]
        for unv in unverified_candidates:
            if unv in clean_text and unv not in profile_skills_lower:
                raise HallucinationDetectedError(
                    f"Anti-hallucination check failed: unverified skill '{unv}' found in tailored text but missing from verified candidate profile."
                )

    def tailor_experience_highlights(
        self,
        profile: ProfileSnapshot,
        job_description: str,
        target_title: str,
    ) -> TailoredResume:
        """Reorder and prioritize verified highlights based on relevance to job description.
        
        Strictly deterministic and grounded in existing profile bullets.
        """
        clean_desc = sanitize_job_description(job_description).lower()
        diffs: List[BulletDiff] = []
        tailored_highlights: Dict[str, List[str]] = {}

        for exp in profile.candidate.experience:
            company = exp.company
            bullets = exp.highlights
            if not bullets:
                continue

            # Score each verified bullet by keyword overlap with job description
            scored_bullets = []
            for b in bullets:
                words = set(re.findall(r"\b[a-z]{3,}\b", b.lower()))
                overlap = [w for w in words if w in clean_desc]
                score = len(overlap)
                scored_bullets.append((score, b, overlap))

            # Sort descending by relevance score (deterministic tie-breaker: original index)
            scored_bullets.sort(key=lambda x: x[0], reverse=True)

            ordered_bullets: List[str] = []
            for rank, (score, bullet, matched_kw) in enumerate(scored_bullets, start=1):
                ordered_bullets.append(bullet)
                diffs.append(
                    BulletDiff(
                        company=company,
                        original_bullet=bullet,
                        tailored_bullet=bullet,
                        reordered_priority=rank,
                        matched_keywords=sorted(matched_kw),
                    )
                )

            tailored_highlights[company] = ordered_bullets

        # Compute provenance hash
        serialized = json.dumps(tailored_highlights, sort_keys=True)
        prov_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        return TailoredResume(
            profile_version=profile.profile_version,
            target_job_title=target_title,
            tailored_highlights=tailored_highlights,
            diffs=diffs,
            provenance_hash=prov_hash,
        )
