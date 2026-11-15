"""Backup, export, and disaster recovery utilities (Phase 2.6).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("worker.ops.backup")


class BackupIntegrityError(Exception):
    """Raised when a backup bundle fails checksum or schema integrity verification."""


class BackupMetadata(BaseModel):
    """Metadata describing a backup archive and its cryptographic checksum."""

    model_config = ConfigDict(extra="forbid")

    backup_id: str = Field(default_factory=lambda: uuid4().hex)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = Field(default="1.0.0")
    item_counts: Dict[str, int] = Field(default_factory=dict)
    checksum_sha256: str = Field(..., description="SHA-256 of canonical JSON payload")


class BackupBundle(BaseModel):
    """Self-contained backup archive containing data records and cryptographic manifest."""

    model_config = ConfigDict(extra="forbid")

    metadata: BackupMetadata
    data: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)


class RestoreResult(BaseModel):
    """Auditable result of restoring data from a backup archive."""

    model_config = ConfigDict(extra="forbid")

    backup_id: str
    restored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    restored_counts: Dict[str, int] = Field(default_factory=dict)
    verified: bool = Field(default=False)
    errors: List[str] = Field(default_factory=list)


def json_default_serializer(obj: Any) -> Any:
    """Format dates, UUIDs, and sets into canonical JSON primitives."""
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, (UUID,)):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(list(obj))
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"Type {type(obj)} is not JSON serializable")


def compute_payload_checksum(data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash over canonical JSON representation."""
    canonical_json = json.dumps(data, sort_keys=True, default=json_default_serializer)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class BackupManager:
    """Manages creation, verification, and recovery of application backups."""

    @staticmethod
    def create_backup(
        answer_bank_entries: Optional[List[Any]] = None,
        profile_snapshots: Optional[List[Any]] = None,
        applications: Optional[List[Any]] = None,
        events: Optional[List[Any]] = None,
        output_path: Optional[Union[str, Path]] = None,
    ) -> BackupBundle:
        """Create an export bundle of core application data with SHA-256 verification."""
        data: Dict[str, List[Dict[str, Any]]] = {
            "answer_bank": [],
            "profile_snapshots": [],
            "applications": [],
            "events": [],
        }

        # Convert entries to dicts if they are Pydantic models
        for item in answer_bank_entries or []:
            data["answer_bank"].append(item.model_dump() if hasattr(item, "model_dump") else dict(item))
        for item in profile_snapshots or []:
            data["profile_snapshots"].append(item.model_dump() if hasattr(item, "model_dump") else dict(item))
        for item in applications or []:
            data["applications"].append(item.model_dump() if hasattr(item, "model_dump") else dict(item))
        for item in events or []:
            data["events"].append(item.model_dump() if hasattr(item, "model_dump") else dict(item))

        counts = {k: len(v) for k, v in data.items()}
        checksum = compute_payload_checksum(data)

        meta = BackupMetadata(
            backup_id=uuid4().hex,
            created_at=datetime.now(timezone.utc),
            schema_version="1.0.0",
            item_counts=counts,
            checksum_sha256=checksum,
        )

        bundle = BackupBundle(metadata=meta, data=data)

        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(bundle.model_dump(), f, indent=2, default=json_default_serializer)
            logger.info("Saved backup %s to %s with checksum %s", meta.backup_id, p, checksum)

        return bundle

    @staticmethod
    def load_backup(source: Union[str, Path, Dict[str, Any]]) -> BackupBundle:
        """Load and parse a backup bundle from file or raw dictionary."""
        if isinstance(source, (str, Path)):
            with open(source, "r", encoding="utf-8") as f:
                raw = json.load(f)
        elif isinstance(source, dict):
            raw = source
        else:
            raise ValueError(f"Unsupported backup source type: {type(source)}")

        return BackupBundle.model_validate(raw)

    @classmethod
    def verify_backup_integrity(cls, bundle: Union[BackupBundle, str, Path, Dict[str, Any]]) -> bool:
        """Verify schema, payload counts, and SHA-256 cryptographic checksum."""
        if not isinstance(bundle, BackupBundle):
            bundle = cls.load_backup(bundle)

        # Check item counts against metadata manifest
        for category, count in bundle.metadata.item_counts.items():
            actual = len(bundle.data.get(category, []))
            if actual != count:
                logger.error(
                    "Backup integrity failure: count mismatch in '%s' (expected=%d, actual=%d)",
                    category,
                    count,
                    actual,
                )
                return False

        # Recompute SHA-256 checksum over data payload
        recomputed = compute_payload_checksum(bundle.data)
        if recomputed != bundle.metadata.checksum_sha256:
            logger.error(
                "Backup integrity failure: checksum mismatch (expected=%s, actual=%s)",
                bundle.metadata.checksum_sha256,
                recomputed,
            )
            return False

        return True

    @classmethod
    def restore_backup(
        cls,
        bundle: Union[BackupBundle, str, Path, Dict[str, Any]],
        target_repositories: Optional[Dict[str, Any]] = None,
    ) -> RestoreResult:
        """Restore records from an archive after verifying cryptographic integrity."""
        if not isinstance(bundle, BackupBundle):
            bundle = cls.load_backup(bundle)

        if not cls.verify_backup_integrity(bundle):
            raise BackupIntegrityError(
                f"Backup {bundle.metadata.backup_id} failed cryptographic integrity verification."
            )

        restored_counts: Dict[str, int] = {}
        errors: List[str] = []

        # If repositories are provided, restore records into their target stores
        repos = target_repositories or {}

        for category, items in bundle.data.items():
            restored_counts[category] = len(items)
            repo = repos.get(category)
            if repo is not None and hasattr(repo, "restore_records"):
                try:
                    repo.restore_records(items)
                except Exception as ex:
                    errors.append(f"Failed to restore {category}: {ex}")

        return RestoreResult(
            backup_id=bundle.metadata.backup_id,
            restored_at=datetime.now(timezone.utc),
            restored_counts=restored_counts,
            verified=True,
            errors=errors,
        )
