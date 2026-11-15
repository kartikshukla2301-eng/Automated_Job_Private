"""Safe Cover Letter Generation with Human Review Requirement and Prompt Sanitization (Phase 1.9).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 6, 8, 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from worker.discovery.security import sanitize_job_description
from worker.profile.exceptions import HallucinationDetectedError
from worker.profile.models import ProfileSnapshot

logger = logging.getLogger("worker.profile.cover_letter")


class CoverLetterDraft(BaseModel):
    """Structured cover letter draft requiring mandatory human review before use."""

    model_config = ConfigDict(extra="forbid")

    candidate_name: str = Field(..., description="Candidate full name")
    company_name: str = Field(..., description="Target company name")
    job_title: str = Field(..., description="Target job title")
    salutation: str = Field(default="Dear Hiring Team,")
    intro_paragraph: str = Field(..., description="Introductory alignment paragraph")
    body_paragraphs: list[str] = Field(default_factory=list, description="Evidence-backed body paragraphs")
    closing_paragraph: str = Field(..., description="Professional sign-off")
    full_text: str = Field(..., description="Complete assembled cover letter draft")
    needs_review: bool = Field(default=True, description="Strictly True: never auto-submitted without human review")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    profile_version: str = Field(..., description="Pinned profile snapshot version")
    provenance_hash: str = Field(..., description="SHA-256 hash of assembled letter")


class CoverLetterGenerator:
    """Generates strictly grounded cover letter drafts from verified candidate facts."""

    def __init__(self) -> None:
        pass

    def generate_draft(
        self,
        profile: ProfileSnapshot,
        company: str,
        job_title: str,
        job_description: str,
    ) -> CoverLetterDraft:
        """Construct grounded, personalized cover letter draft.
        
        Sanitizes untrusted job description against prompt injection breakout.
        """
        clean_desc = sanitize_job_description(job_description)
        cand = profile.candidate

        # Select relevant experience and skills
        top_skills = [s.name for s in cand.skills[:4]]
        skills_str = ", ".join(top_skills) if top_skills else "software engineering"

        current_role = "Software Engineer"
        if cand.experience:
            current_role = cand.experience[0].title

        salutation = f"Dear {company} Hiring Team,"

        intro = (
            f"I am writing to express my strong interest in the {job_title} position at {company}. "
            f"With verified experience as a {current_role} specializing in {skills_str}, "
            f"I am eager to contribute to your engineering goals."
        )

        body_paragraphs: list[str] = []
        if cand.experience:
            primary_exp = cand.experience[0]
            highlights_summary = " ".join(primary_exp.highlights[:2]) if primary_exp.highlights else ""
            body_paragraphs.append(
                f"In my role as {primary_exp.title} at {primary_exp.company}, {highlights_summary}"
            )

        if cand.projects:
            proj = cand.projects[0]
            tech_str = ", ".join(proj.technologies) if proj.technologies else ""
            body_paragraphs.append(
                f"Additionally, on my project '{proj.title}', I utilized {tech_str} to solve real-world architectural challenges."
            )

        closing = (
            f"Thank you for considering my application. I look forward to the possibility of discussing "
            f"how my background in {skills_str} aligns with the needs of {company}."
        )

        full_letter = f"{salutation}\n\n{intro}\n\n" + "\n\n".join(body_paragraphs) + f"\n\n{closing}\n\nSincerely,\n{cand.name}"

        prov_hash = hashlib.sha256(full_letter.encode("utf-8")).hexdigest()

        return CoverLetterDraft(
            candidate_name=cand.name,
            company_name=company,
            job_title=job_title,
            salutation=salutation,
            intro_paragraph=intro,
            body_paragraphs=body_paragraphs,
            closing_paragraph=closing,
            full_text=full_letter,
            needs_review=True,
            profile_version=profile.profile_version,
            provenance_hash=prov_hash,
        )
