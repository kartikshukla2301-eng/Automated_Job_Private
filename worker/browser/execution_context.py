"""Execution context coordinating browser inspection, Answer Bank mapping, and fill planning.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 7, 8, 11, 12)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from worker.answers.models import ResolutionStatus
from worker.answers.resolver import AnswerResolver
from worker.browser.browser_session import BrowserSession
from worker.browser.evidence import EvidenceCollector, InspectionEvidence
from worker.browser.exceptions import UnsafeActionError
from worker.browser.field_detector import DetectedField
from worker.browser.fill_plan import FillPlan, PlannedField, ResolutionOutcome
from worker.browser.navigation_guard import NavigationGuard
from worker.browser.page_inspector import PageInspector
from worker.policy.engine import PolicyEngine
from worker.policy.taxonomy import (
    CATEGORY_KEYWORD_RULES,
    SENSITIVE_SECURITY_KEYWORDS,
    FieldCategory,
    PolicyType,
)
from worker.profile.models import ProfileSnapshot

logger = logging.getLogger("worker.browser.execution_context")


class ExecutionContext:
    """Orchestrates safe L0 form inspection and fill plan generation."""

    def __init__(
        self,
        session: BrowserSession,
        navigation_guard: Optional[NavigationGuard] = None,
        page_inspector: Optional[PageInspector] = None,
        evidence_collector: Optional[EvidenceCollector] = None,
        answer_resolver: Optional[AnswerResolver] = None,
        policy_engine: Optional[PolicyEngine] = None,
        profile: Optional[ProfileSnapshot] = None,
    ) -> None:
        self.session = session
        self.navigation_guard = navigation_guard or NavigationGuard()
        self.page_inspector = page_inspector or PageInspector()
        self.evidence_collector = evidence_collector or EvidenceCollector()
        self.answer_resolver = answer_resolver
        self.policy_engine = policy_engine or PolicyEngine()
        self.profile = profile

    async def inspect_and_plan(
        self,
        target_url: str,
        provider_name: str = "greenhouse",
        job_id: Optional[UUID] = None,
    ) -> Tuple[FillPlan, InspectionEvidence]:
        """Execute safe L0 form inspection without entering candidate data or submitting.

        SAFETY INVARIANTS:
        - NEVER types real candidate data into external form elements.
        - NEVER clicks submit, apply, or finish.
        - NEVER dispatches form submission.
        - Fails closed on sensitive fields (passwords, OTP, MFA, SSN, bank credentials).
        """
        self.session.ensure_active()

        # Step 1: Validate navigation target against approved provider origins
        validated_uri = self.navigation_guard.validate_url(target_url)

        # Step 2: Navigate to target page
        logger.info("Session %s navigating to %s", self.session.session_id, validated_uri)
        try:
            await self.session.page.goto(
                validated_uri,
                timeout=self.session.timeout_ms,
                wait_until="load",
            )
        except Exception as exc:
            logger.error("Navigation failed for %s: %s", validated_uri, exc)
            raise

        # Check page title
        try:
            page_title = await self.session.page.title()
        except Exception:
            page_title = "Application Page"

        # Step 3: Inspect DOM and detect form fields
        detected_fields: List[DetectedField] = await self.page_inspector.inspect_page(self.session.page)
        logger.info("Detected %d form fields on %s", len(detected_fields), validated_uri)

        # Step 4: Map fields to Answer Bank and Policy Engine
        planned_fields: List[PlannedField] = []
        for field in detected_fields:
            planned = self._plan_field(field, provider_name=provider_name)
            planned_fields.append(planned)

        # Step 5: Compile FillPlan
        auto_approved = sum(1 for f in planned_fields if f.resolution_outcome == ResolutionOutcome.AUTO_APPROVED)
        needs_review = sum(1 for f in planned_fields if f.resolution_outcome in (ResolutionOutcome.NEEDS_REVIEW, ResolutionOutcome.NEEDS_CONFIRMATION))
        blocked = sum(1 for f in planned_fields if f.resolution_outcome == ResolutionOutcome.POLICY_BLOCKED)
        unresolved = sum(1 for f in planned_fields if f.resolution_outcome in (ResolutionOutcome.NO_MATCH, ResolutionOutcome.AMBIGUOUS, ResolutionOutcome.UNSUPPORTED))

        fill_plan = FillPlan(
            session_id=self.session.session_id,
            job_id=job_id,
            canonical_url=target_url,
            page_title=page_title,
            fields=planned_fields,
            total_fields=len(planned_fields),
            auto_approved_count=auto_approved,
            needs_review_count=needs_review,
            blocked_count=blocked,
            unresolved_count=unresolved,
        )

        # Step 6: Capture evidence screenshot
        screenshot_path = await self.evidence_collector.capture_screenshot(
            page=self.session.page,
            session_id=self.session.session_id,
            prefix=f"{provider_name}_l0_inspection",
        )

        # Step 7: Compile InspectionEvidence
        evidence = InspectionEvidence(
            session_id=self.session.session_id,
            job_id=job_id,
            provider=provider_name,
            canonical_url=target_url,
            page_title=page_title,
            detected_field_count=len(detected_fields),
            resolved_field_count=auto_approved,
            unresolved_field_count=unresolved,
            blocked_field_count=blocked,
            outcome="L0_INSPECTION_COMPLETED",
            screenshot_path=screenshot_path,
            fill_plan_id=fill_plan.plan_id,
            metadata={
                "auto_approved": auto_approved,
                "needs_review": needs_review,
                "blocked": blocked,
                "unresolved": unresolved,
                "is_executable": fill_plan.is_executable(),
            },
        )

        return fill_plan, evidence

    def _plan_field(self, field: DetectedField, provider_name: str) -> PlannedField:
        """Map single DetectedField through Taxonomy, AnswerResolver, and PolicyEngine."""
        # Check sensitive credentials first
        if field.is_sensitive:
            return PlannedField(
                field_id=field.field_id,
                detected_field=field,
                proposed_answer_ref=None,
                resolution_outcome=ResolutionOutcome.POLICY_BLOCKED,
                policy_type=PolicyType.NEVER_FILL,
                field_category=FieldCategory.SENSITIVE_SECURITY,
                confidence=1.0,
                explanation="Sensitive credential, security code, or identity field strictly blocked from automation.",
                required_user_action="Manual entry required by user during live application.",
                is_safe_to_prefill=False,
            )

        # Evaluate policy and category using PolicyEngine
        policy_decision = self.policy_engine.evaluate(
            field_key=field.field_id,
            label_text=field.label,
        )
        category = policy_decision.category

        # Enforce never_fill policy
        if policy_decision.policy == PolicyType.NEVER_FILL:
            return PlannedField(
                field_id=field.field_id,
                detected_field=field,
                proposed_answer_ref=None,
                resolution_outcome=ResolutionOutcome.POLICY_BLOCKED,
                policy_type=PolicyType.NEVER_FILL,
                field_category=category,
                confidence=1.0,
                explanation=f"PolicyEngine locked policy for {category.value} is NEVER_FILL.",
                required_user_action="Manual candidate intervention required.",
                is_safe_to_prefill=False,
            )

        # Try resolving from candidate profile first
        profile_ref, profile_found = self._resolve_from_profile(field)
        if profile_found:
            outcome = ResolutionOutcome.AUTO_APPROVED if policy_decision.policy in (
                PolicyType.AUTO,
                PolicyType.AUTO_LOG,
            ) else ResolutionOutcome.NEEDS_REVIEW

            return PlannedField(
                field_id=field.field_id,
                detected_field=field,
                proposed_answer_ref=profile_ref,
                resolution_outcome=outcome,
                policy_type=policy_decision.policy,
                field_category=category,
                confidence=0.95,
                explanation=f"Truthfully resolved from candidate ProfileSnapshot ({profile_ref}).",
                required_user_action=None if outcome == ResolutionOutcome.AUTO_APPROVED else "Confirmation required.",
                is_safe_to_prefill=True,
            )

        # Try resolving from AnswerResolver if configured
        if self.answer_resolver:
            res = self.answer_resolver.resolve_field(
                field_key=field.field_id,
                label_text=field.label,
                scope=f"provider:{provider_name}",
            )

            if res.status in (ResolutionStatus.RESOLVED, ResolutionStatus.NEEDS_USER_INPUT) and res.entry:
                if res.entry.needs_review or res.status == ResolutionStatus.NEEDS_USER_INPUT or policy_decision.policy == PolicyType.ALWAYS_ASK:
                    outcome = ResolutionOutcome.NEEDS_REVIEW
                elif policy_decision.policy in (PolicyType.AUTO, PolicyType.AUTO_LOG):
                    outcome = ResolutionOutcome.AUTO_APPROVED
                else:
                    outcome = ResolutionOutcome.NEEDS_CONFIRMATION

                return PlannedField(
                    field_id=field.field_id,
                    detected_field=field,
                    proposed_answer_ref=f"answers:{res.entry.key}",
                    resolution_outcome=outcome,
                    policy_type=policy_decision.policy,
                    field_category=category,
                    confidence=res.entry.confidence,
                    explanation=f"Resolved from Answer Bank entry '{res.entry.key}' (status={res.status.value}).",
                    required_user_action=None if outcome == ResolutionOutcome.AUTO_APPROVED else "User review required.",
                    is_safe_to_prefill=True,
                )

            if res.status == ResolutionStatus.AMBIGUOUS:
                return PlannedField(
                    field_id=field.field_id,
                    detected_field=field,
                    proposed_answer_ref=None,
                    resolution_outcome=ResolutionOutcome.AMBIGUOUS,
                    policy_type=policy_decision.policy,
                    field_category=category,
                    confidence=0.5,
                    explanation="Multiple ambiguous answers found in Answer Bank.",
                    required_user_action="User disambiguation required.",
                    is_safe_to_prefill=False,
                )

        # Unresolved fallback
        outcome = ResolutionOutcome.NO_MATCH
        explanation = "Field could not be resolved from Profile or Answer Bank."
        if field.required:
            action = "Mandatory field requires candidate input before submission."
        else:
            action = "Optional field may be left blank or filled manually."

        return PlannedField(
            field_id=field.field_id,
            detected_field=field,
            proposed_answer_ref=None,
            resolution_outcome=outcome,
            policy_type=policy_decision.policy,
            field_category=category,
            confidence=0.0,
            explanation=explanation,
            required_user_action=action,
            is_safe_to_prefill=False,
        )

    def _resolve_from_profile(self, field: DetectedField) -> Tuple[Optional[str], bool]:
        """Resolve candidate fact reference from ProfileSnapshot."""
        if not self.profile or not self.profile.candidate:
            return None, False

        clean_text = f"{field.label} {field.name or ''} {field.html_id or ''}".lower()

        if "first_name" in clean_text or "first name" in clean_text:
            return "profile:candidate.first_name", True
        if "last_name" in clean_text or "last name" in clean_text:
            return "profile:candidate.last_name", True
        if "email" in clean_text:
            return "profile:candidate.email", True
        if "phone" in clean_text or "tel" in clean_text:
            if self.profile.candidate.phone:
                return "profile:candidate.phone", True
        if "linkedin" in clean_text:
            if "linkedin" in self.profile.candidate.links:
                return "profile:candidate.links.linkedin", True
        if "github" in clean_text:
            if "github" in self.profile.candidate.links:
                return "profile:candidate.links.github", True
        if "portfolio" in clean_text or "website" in clean_text:
            if "portfolio" in self.profile.candidate.links or "website" in self.profile.candidate.links:
                return "profile:candidate.links.portfolio", True

        return None, False

    def _classify_field_category(self, field: DetectedField) -> FieldCategory:
        """Deterministically map field text to fixed 12-category taxonomy."""
        clean_text = f"{field.label} {field.name or ''} {field.html_id or ''}".lower()

        for kw in SENSITIVE_SECURITY_KEYWORDS:
            if kw in clean_text:
                return FieldCategory.SENSITIVE_SECURITY

        for cat, keywords in CATEGORY_KEYWORD_RULES.items():
            if any(kw in clean_text for kw in keywords):
                return cat

        return FieldCategory.UNKNOWN_UNCLASSIFIED
