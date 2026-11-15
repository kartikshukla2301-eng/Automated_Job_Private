"""Resume version management, metadata tracking, and duplicate detection (Phase 1.9).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 6, 8, 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("worker.profile.resume_manager")


class ResumeMetadata(BaseModel):
    """Metadata tracking a specific resume version."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str = Field(..., description="Original filename (e.g. resume_backend.pdf)")
    role_family: str = Field(..., description="Target role domain: backend, platform, fullstack, general")
    content_hash: str = Field(..., description="SHA-256 hash of file content")
    file_path: str = Field(..., description="Local path to stored resume file")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_default: bool = Field(default=False, description="Whether this is the default fallback resume")


class DuplicateResumeError(Exception):
    """Raised when registering an identical resume file content hash."""
    pass


class ResumeNotFoundError(Exception):
    """Raised when requested resume cannot be found."""
    pass


class ResumeManager:
    """Manages versioned resumes, duplicate detection, and role-family matching."""

    def __init__(
        self,
        storage_dir: Path = Path("worker/profile/resumes"),
        metadata_file: Optional[Path] = None,
    ) -> None:
        self.storage_dir = storage_dir
        self.metadata_file = metadata_file or (storage_dir / "resumes_meta.json")

    def _load_metadata(self) -> List[Dict[str, Any]]:
        if not self.metadata_file.exists():
            return []
        try:
            return json.loads(self.metadata_file.read_text(encoding="utf-8"))
        except Exception as err:
            logger.warning("Could not read resume metadata file: %s", err)
            return []

    def _save_metadata(self, records: List[Dict[str, Any]]) -> None:
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_file.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def register_resume(
        self,
        source_path: Path,
        role_family: str,
        is_default: bool = False,
    ) -> ResumeMetadata:
        """Register a new resume version, calculating hash and copying to storage."""
        if not source_path.exists():
            raise FileNotFoundError(f"Source resume file not found: {source_path}")

        file_bytes = source_path.read_bytes()
        content_hash = hashlib.sha256(file_bytes).hexdigest()

        existing = self._load_metadata()
        for r in existing:
            if r.get("content_hash") == content_hash:
                raise DuplicateResumeError(
                    f"Duplicate resume detected: identical content hash exists ({r.get('id')})"
                )

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        dest_filename = f"{content_hash[:12]}_{source_path.name}"
        dest_path = self.storage_dir / dest_filename
        dest_path.write_bytes(file_bytes)

        # If setting as default, clear existing defaults
        if is_default:
            for r in existing:
                r["is_default"] = False

        meta = ResumeMetadata(
            filename=source_path.name,
            role_family=role_family.lower().strip(),
            content_hash=content_hash,
            file_path=str(dest_path),
            is_default=is_default,
        )

        existing.append(meta.model_dump(mode="json"))
        self._save_metadata(existing)
        logger.info("Registered resume version %s (%s)", meta.id, meta.role_family)
        return meta

    def list_resumes(self) -> List[ResumeMetadata]:
        """List all registered resumes."""
        records = self._load_metadata()
        return [ResumeMetadata(**r) for r in records]

    def get_resume(self, resume_id: str) -> ResumeMetadata:
        """Find a resume by its unique identifier."""
        resumes = self.list_resumes()
        for r in resumes:
            if r.id == resume_id:
                return r
        raise ResumeNotFoundError(f"Resume not found for ID: {resume_id}")

    def select_resume_for_job(self, job_title: str) -> Optional[ResumeMetadata]:
        """Match appropriate resume version using job title keyword classification."""
        resumes = self.list_resumes()
        if not resumes:
            return None

        title_lower = job_title.lower()

        # Role family detection
        detected_family = "general"
        if any(k in title_lower for k in ("platform", "sre", "devops", "infrastructure", "cloud")):
            detected_family = "platform"
        elif any(k in title_lower for k in ("backend", "distributed", "systems", "api", "python", "golang")):
            detected_family = "backend"
        elif any(k in title_lower for k in ("frontend", "fullstack", "full stack", "react", "next.js", "web")):
            detected_family = "fullstack"

        # 1. Match detected family
        for r in resumes:
            if r.role_family == detected_family:
                return r

        # 2. Match default resume
        for r in resumes:
            if r.is_default:
                return r

        # 3. Fallback to first available resume
        return resumes[0]
