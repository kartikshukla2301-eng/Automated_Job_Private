"""Pilot Orchestrator for Supervised L0 Live Form Validation (Phase 2.1).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11, Section 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from worker.answers.resolver import AnswerResolver
from worker.pilot.evidence import PilotEvidenceManager
from worker.pilot.models import PilotFormRecord, PilotQualityReport, PilotReviewRequest, PilotReviewStatus
from worker.policy.engine import PolicyEngine
from worker.profile.models import ProfileSnapshot
from worker.providers.base import FormField
from worker.providers.registry import ProviderRegistry, create_default_registry

logger = logging.getLogger("worker.pilot.orchestrator")


class PilotOrchestrator:
    """Orchestrates operator-supervised L0 form inspections, evidence storage, and human review."""

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        evidence_manager: Optional[PilotEvidenceManager] = None,
        policy_engine: Optional[PolicyEngine] = None,
        answer_resolver: Optional[AnswerResolver] = None,
        records_storage_path: Optional[Path] = None,
    ) -> None:
        self.registry = registry or create_default_registry()
        self.evidence_manager = evidence_manager or PilotEvidenceManager()
        self.policy_engine = policy_engine or PolicyEngine()
        self.answer_resolver = answer_resolver
        self.storage_path = records_storage_path or Path("worker/evidence/pilot_records.json")
        self._records: Dict[UUID, PilotFormRecord] = {}
        self._load_records()

    def _load_records(self) -> None:
        """Load stored inspection records from disk."""
        if not self.storage_path.exists():
            return
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
            for item in raw:
                rec = PilotFormRecord.model_validate(item)
                self._records[rec.id] = rec
        except Exception as e:
            logger.error("Failed to load pilot records from %s: %s", self.storage_path, e)

    def _save_records(self) -> None:
        """Persist inspection records to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.model_dump(mode="json") for r in self._records.values()]
        self.storage_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    async def inspect_form(
        self,
        user_id: UUID,
        provider_name: str,
        job_url: str,
        company: str,
        title: str,
        profile: ProfileSnapshot,
        page: Optional[Any] = None,
        html_content: Optional[str] = None,
        job_id: Optional[str] = None,
        is_live_page: bool = True,
    ) -> PilotFormRecord:
        """Execute safe L0 form inspection, build fill plan without submitting, and record evidence."""
        norm_provider = provider_name.strip().lower()
        provider = self.registry.get_provider(norm_provider)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' is not registered in ProviderRegistry.")

        # Discovered fields and policy evaluations
        discovered_fields: List[FormField] = []
        fill_plan: Dict[str, Any] = {}
        policy_decisions: Dict[str, Any] = {}
        screenshot_bytes: Optional[bytes] = None

        if page is not None:
            # Browser inspection via provider
            fill_result = await provider.inspect_and_fill(
                page=page,
                profile=profile,
                dry_run=True,
            )
            discovered_fields = fill_result.discovered_fields
            fill_plan = fill_result.fields_filled
            try:
                screenshot_bytes = await page.screenshot(full_page=True)
            except Exception as e:
                logger.warning("Could not capture screenshot: %s", e)
        elif html_content is not None and norm_provider == "greenhouse":
            from worker.providers.greenhouse import parse_greenhouse_form_html
            discovered_fields = parse_greenhouse_form_html(
                html_content,
                profile=profile,
                answer_resolver=self.answer_resolver,
                policy_engine=self.policy_engine,
            )
            for f in discovered_fields:
                if f.is_resolved and f.policy_approved:
                    fill_plan[f.label] = f.resolved_value
        else:
            # Fallback inspection representation
            pass

        # Calculate counts
        fields_count = len(discovered_fields)
        resolved_count = sum(1 for f in discovered_fields if f.is_resolved and f.policy_approved)
        unresolved_count = sum(1 for f in discovered_fields if not f.is_resolved and f.policy != "never_fill")
        policy_blocked_count = sum(1 for f in discovered_fields if not f.policy_approved or f.policy == "never_fill")
        sensitive_count = sum(1 for f in discovered_fields if f.classification == "sensitive_security")

        record_id = uuid4()
        schema_snapshot = [f.model_dump(mode="json") for f in discovered_fields]
        for f in discovered_fields:
            policy_decisions[f.field_id] = {
                "policy": f.policy,
                "classification": f.classification,
                "approved": f.policy_approved,
            }

        # Store evidence bundle
        evidence_dir = self.evidence_manager.store_evidence(
            record_id=record_id,
            user_id=user_id,
            provider=norm_provider,
            job_url=job_url,
            schema_snapshot=schema_snapshot,
            fill_plan=fill_plan,
            policy_decisions=policy_decisions,
            screenshot_bytes=screenshot_bytes,
        )

        hasher = hashlib.sha256()
        hasher.update(json.dumps(schema_snapshot, sort_keys=True, default=str).encode("utf-8"))
        audit_hash = hasher.hexdigest()

        record = PilotFormRecord(
            id=record_id,
            user_id=user_id,
            provider=norm_provider,
            job_id=job_id or str(uuid4()),
            job_url=job_url,
            company=company,
            title=title,
            fields_count=fields_count,
            resolved_count=resolved_count,
            unresolved_count=unresolved_count,
            policy_blocked_count=policy_blocked_count,
            sensitive_fields_count=sensitive_count,
            evidence_dir=str(evidence_dir),
            screenshot_path=str(evidence_dir / "screenshot.png") if screenshot_bytes else None,
            schema_snapshot=schema_snapshot,
            fill_plan=fill_plan,
            review_status=PilotReviewStatus.PENDING,
            is_live_page=is_live_page,
            audit_hash=audit_hash,
        )

        self._records[record.id] = record
        self._save_records()
        return record

    def record_human_review(
        self,
        record_id: UUID,
        review_request: PilotReviewRequest,
    ) -> PilotFormRecord:
        """Record human operator review feedback for an inspected form."""
        if record_id not in self._records:
            raise KeyError(f"Pilot record '{record_id}' not found.")

        rec = self._records[record_id]
        rec.review_status = review_request.status
        rec.reviewed_at = datetime.now(timezone.utc)
        rec.reviewer_id = review_request.reviewer_id
        rec.reviewer_notes = review_request.notes
        rec.incorrect_mappings_count = review_request.incorrect_mappings_count
        rec.wrong_sensitive_count = review_request.wrong_sensitive_count

        self._records[record_id] = rec
        self._save_records()
        return rec

    def get_record(self, record_id: UUID) -> Optional[PilotFormRecord]:
        """Fetch a specific inspection record."""
        return self._records.get(record_id)

    def list_records(self, user_id: Optional[UUID] = None) -> List[PilotFormRecord]:
        """List inspection records, optionally filtered by user."""
        records = list(self._records.values())
        if user_id:
            records = [r for r in records if r.user_id == user_id]
        return sorted(records, key=lambda r: r.inspected_at, reverse=True)

    def generate_quality_report(self) -> PilotQualityReport:
        """Calculate truthful pilot metrics and locked gate readiness.

        ACCURACY METHODOLOGY:
        Accuracy = max(0.0, (total_reviewed_resolved - total_incorrect_mappings) / total_reviewed_resolved * 100)
        Unresolved fields are NOT counted as correct mappings.
        """
        all_records = list(self._records.values())
        distinct_urls = set(r.job_url for r in all_records)
        duplicate_count = len(all_records) - len(distinct_urls)

        reviewed = [r for r in all_records if r.review_status in (PilotReviewStatus.APPROVED, PilotReviewStatus.REJECTED, PilotReviewStatus.FLAGGED)]
        pending = [r for r in all_records if r.review_status == PilotReviewStatus.PENDING]

        total_reviewed_fields = sum(r.fields_count for r in reviewed)
        total_reviewed_resolved = sum(r.resolved_count for r in reviewed)
        total_incorrect = sum(r.incorrect_mappings_count for r in reviewed)
        total_wrong_sensitive = sum(r.wrong_sensitive_count for r in reviewed)

        if total_reviewed_resolved > 0:
            accuracy = max(0.0, float(total_reviewed_resolved - total_incorrect) / float(total_reviewed_resolved) * 100.0)
        else:
            accuracy = 0.0

        provider_breakdown: Dict[str, Dict[str, Any]] = {}
        for r in all_records:
            p = r.provider
            if p not in provider_breakdown:
                provider_breakdown[p] = {
                    "total": 0,
                    "reviewed": 0,
                    "resolved": 0,
                    "incorrect": 0,
                    "unresolved": 0,
                }
            provider_breakdown[p]["total"] += 1
            if r.review_status != PilotReviewStatus.PENDING:
                provider_breakdown[p]["reviewed"] += 1
                provider_breakdown[p]["resolved"] += r.resolved_count
                provider_breakdown[p]["incorrect"] += r.incorrect_mappings_count
                provider_breakdown[p]["unresolved"] += r.unresolved_count

        # Gate readiness requires >=20 distinct reviewed forms, accuracy >= 98%, 0 wrong sensitive
        is_ready = (
            len(distinct_urls) >= 20
            and len(reviewed) >= 20
            and accuracy >= 98.0
            and total_wrong_sensitive == 0
        )

        return PilotQualityReport(
            total_inspections=len(all_records),
            distinct_forms_inspected=len(distinct_urls),
            forms_reviewed=len(reviewed),
            forms_pending_review=len(pending),
            total_reviewed_fields=total_reviewed_fields,
            total_reviewed_resolved=total_reviewed_resolved,
            total_incorrect_mappings=total_incorrect,
            total_wrong_sensitive_answers=total_wrong_sensitive,
            reviewed_field_accuracy=round(accuracy, 2),
            provider_breakdown=provider_breakdown,
            duplicate_records_detected=max(0, duplicate_count),
            is_gate_ready=is_ready,
        )
