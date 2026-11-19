"""Form Snapshot Recording & Offline Replay (Phase 4.2, OI-2).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14 `form_snapshots`;
  Part I.4 Optional Improvement OI-2: "Record/replay fixtures: save sanitised form HTML
  (form_snapshots) and replay them offline in regression tests.")
- docs/BUILD_RULES.md

Persists only the *sanitised structure* of an inspected form (field ids, labels, types,
required flag, options, taxonomy classification, policy) — never a candidate's resolved
answers, raw HTML, or audit metadata. This mirrors the "Sanitised form DOM structure"
description of the `form_snapshots` table (Architecture Section 14) and lets a later
regression test replay a previously captured structure to detect drift, offline, without
a live browser or network access.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

from worker.providers.base import FormField

logger = logging.getLogger("worker.browser.form_snapshot")

# worker/sessions/ is gitignored (see .gitignore: "worker/sessions/*"); reusing it keeps
# locally captured snapshots out of version control without inventing a new ignore rule.
DEFAULT_SNAPSHOT_DIR = Path("worker/sessions/form_snapshots")


class SanitizedFormField(BaseModel):
    """Structure-only projection of a `FormField` — never includes resolved answers."""

    model_config = ConfigDict(extra="forbid")

    field_id: str
    name: Optional[str] = None
    label: str
    field_type: str
    required: bool
    options: List[str] = Field(default_factory=list)
    classification: Optional[str] = None
    policy: str

    @classmethod
    def from_form_field(cls, field: FormField) -> "SanitizedFormField":
        return cls(
            field_id=field.field_id,
            name=field.name,
            label=field.label,
            field_type=field.field_type,
            required=field.required,
            options=list(field.options),
            classification=field.classification.value if field.classification else None,
            policy=field.policy.value,
        )


class FormSnapshot(BaseModel):
    """Sanitised, replayable snapshot of a provider's form structure at a point in time."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    application_id: Optional[str] = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str
    fields: List[SanitizedFormField]


def _hashable_field_tuple(f: SanitizedFormField) -> tuple:
    return (
        f.field_id,
        f.name or "",
        f.label,
        f.field_type,
        f.required,
        tuple(f.options),
        f.classification or "",
        f.policy,
    )


def compute_form_structure_hash(fields: List[SanitizedFormField]) -> str:
    """Deterministic SHA-256 hash over the sanitised field structure (order-independent)."""
    canonical = sorted(_hashable_field_tuple(f) for f in fields)
    payload = json.dumps(canonical, sort_keys=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_form_snapshot(
    provider: str,
    discovered_fields: List[FormField],
    application_id: Optional[str] = None,
    captured_at: Optional[datetime] = None,
) -> FormSnapshot:
    """Build a sanitised, structure-only snapshot from freshly inspected form fields.

    Never persists `resolved_value` or `audit_metadata` — only the structural shape
    needed to detect drift later (ids, labels, types, required flag, options,
    taxonomy classification, policy).
    """
    sanitized = [SanitizedFormField.from_form_field(f) for f in discovered_fields]
    return FormSnapshot(
        provider=provider,
        application_id=application_id,
        captured_at=captured_at or datetime.now(timezone.utc),
        content_hash=compute_form_structure_hash(sanitized),
        fields=sanitized,
    )


class FormSnapshotRepository(Protocol):
    """Protocol for persisting and replaying sanitised form snapshots."""

    def save(self, snapshot: FormSnapshot) -> None: ...

    def latest(self, provider: str) -> Optional[FormSnapshot]: ...

    def all_for_provider(self, provider: str) -> List[FormSnapshot]: ...


class FileFormSnapshotRepository:
    """Thread-safe, append-only JSONL-backed form snapshot store (one file per provider)."""

    def __init__(self, snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR) -> None:
        self.snapshot_dir = snapshot_dir
        self._lock = threading.Lock()

    def _path_for(self, provider: str) -> Path:
        return self.snapshot_dir / f"{provider.lower()}.jsonl"

    def save(self, snapshot: FormSnapshot) -> None:
        path = self._path_for(snapshot.provider)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(snapshot.model_dump_json() + "\n")
        logger.info(
            "Saved form snapshot for provider=%s hash=%s fields=%d",
            snapshot.provider,
            snapshot.content_hash,
            len(snapshot.fields),
        )

    def all_for_provider(self, provider: str) -> List[FormSnapshot]:
        path = self._path_for(provider)
        if not path.exists():
            return []
        with self._lock:
            lines = path.read_text(encoding="utf-8").splitlines()
        return [FormSnapshot.model_validate(json.loads(line)) for line in lines if line.strip()]

    def latest(self, provider: str) -> Optional[FormSnapshot]:
        snapshots = self.all_for_provider(provider)
        return snapshots[-1] if snapshots else None


class SnapshotDriftResult(BaseModel):
    """Result of replaying a saved snapshot against a freshly parsed form structure."""

    model_config = ConfigDict(extra="forbid")

    drifted: bool
    baseline_hash: str
    current_hash: str
    added_field_ids: List[str] = Field(default_factory=list)
    removed_field_ids: List[str] = Field(default_factory=list)


def detect_drift(baseline: FormSnapshot, current_fields: List[FormField]) -> SnapshotDriftResult:
    """Replay a saved snapshot against freshly inspected fields to detect structural drift.

    This is the offline regression check behind OI-2: a previously recorded, sanitised
    form structure is replayed (no browser/network needed) and compared field-by-field
    against a current parse of the same fixture or live form.
    """
    current_sanitized = [SanitizedFormField.from_form_field(f) for f in current_fields]
    current_hash = compute_form_structure_hash(current_sanitized)

    baseline_ids = {f.field_id for f in baseline.fields}
    current_ids = {f.field_id for f in current_sanitized}

    return SnapshotDriftResult(
        drifted=current_hash != baseline.content_hash,
        baseline_hash=baseline.content_hash,
        current_hash=current_hash,
        added_field_ids=sorted(current_ids - baseline_ids),
        removed_field_ids=sorted(baseline_ids - current_ids),
    )
