"""Lever job provider adapter and form execution foundation.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 11, 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from worker.answers.models import ResolutionStatus
from worker.answers.resolver import AnswerResolver
from worker.core.exceptions import RealSubmitGateBlockedError
from worker.policy.engine import PolicyEngine
from worker.policy.taxonomy import FieldCategory, PolicyType
from worker.profile.models import ProfileSnapshot
from worker.providers.base import FormField, FormFillResult, JobProvider

logger = logging.getLogger("worker.providers.lever")


class LeverProvider(JobProvider):
    """Playwright-based provider for inspecting Lever job applications.
    
    Adheres strictly to L0 dry-run safety and never mutates forms or clicks submit.
    """

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        answer_resolver: Optional[AnswerResolver] = None,
    ) -> None:
        from worker.answers.repository import InMemoryAnswerBankRepository

        self.policy_engine = policy_engine or PolicyEngine()
        self.repository = InMemoryAnswerBankRepository()
        self.answer_resolver = answer_resolver or AnswerResolver(
            repository=self.repository,
            policy_engine=self.policy_engine,
        )

    async def inspect_form(self, page: Any) -> List[FormField]:
        """Inspect Lever application form and extract form controls."""
        from worker.browser.page_inspector import PageInspector

        inspector = PageInspector()
        html = await page.content() if hasattr(page, "content") else ""
        detected = inspector.inspect_html(html)

        discovered_fields: List[FormField] = []
        for d in detected:
            decision = self.policy_engine.evaluate(field_key=d.name or d.field_id, label_text=d.label)
            cat = decision.category
            policy = decision.policy

            discovered_fields.append(
                FormField(
                    field_id=d.field_id,
                    name=d.name,
                    label=d.label,
                    field_type=d.input_type,
                    required=d.required,
                    options=d.options,
                    classification=cat,
                    policy=policy,
                    policy_approved=(policy in (PolicyType.AUTO, PolicyType.AUTO_LOG)),
                )
            )
        return discovered_fields

    async def fill_form(
        self,
        page: Any,
        profile: ProfileSnapshot,
        fields: List[FormField],
        screenshot_dir: Optional[Path] = None,
    ) -> FormFillResult:
        """Execute L0 dry-run form plan without typing or clicking into DOM."""
        from worker.browser.page_inspector import PageInspector

        inspector = PageInspector()
        html = await page.content() if hasattr(page, "content") else ""
        detected = inspector.inspect_html(html)

        discovered: List[FormField] = []
        fields_filled: Dict[str, str] = {}
        unresolved: List[str] = []

        for d in detected:
            decision = self.policy_engine.evaluate(field_key=d.name or d.field_id, label_text=d.label)
            cat = decision.category
            policy = decision.policy

            res = self.answer_resolver.resolve_with_profile_fallback(
                field_key=d.name or d.field_id,
                label_text=d.label,
                profile=profile,
                scope="provider:lever",
            )
            is_res = (res.status == ResolutionStatus.RESOLVED and res.resolved_value is not None)
            resolved_val = res.resolved_value if is_res else None

            form_field = FormField(
                field_id=d.field_id,
                name=d.name,
                label=d.label,
                field_type=d.input_type,
                required=d.required,
                options=d.options,
                classification=cat,
                policy=policy,
                resolution_status=ResolutionStatus.RESOLVED if is_res else ResolutionStatus.NO_MATCH,
                resolved_value=resolved_val,
                is_resolved=is_res,
                policy_approved=(policy in (PolicyType.AUTO, PolicyType.AUTO_LOG)),
            )
            discovered.append(form_field)

            if is_res and form_field.policy_approved:
                fields_filled[d.label] = str(resolved_val)
            elif d.required:
                unresolved.append(d.label)

        screenshot_path = None
        if screenshot_dir and hasattr(page, "screenshot"):
            try:
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                p = screenshot_dir / f"lever_evidence_{uuid.uuid4().hex[:8]}.png"
                await page.screenshot(path=str(p))
                screenshot_path = str(p)
            except Exception as ss_err:
                logger.warning("Could not capture screenshot: %s", ss_err)

        return FormFillResult(
            success=len(unresolved) == 0,
            discovered_fields=discovered,
            fields_filled=fields_filled,
            unresolved_required_fields=unresolved,
            evidence_screenshot_path=screenshot_path,
        )

    async def submit_application(self, page: Any) -> bool:
        """Submission is strictly disabled by non-negotiable safety invariant."""
        raise RealSubmitGateBlockedError(
            "Real submission is permanently disabled: real_submit_gate_enabled = False"
        )
