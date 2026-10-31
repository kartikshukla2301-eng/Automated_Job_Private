"""Centralized code-enforced PolicyEngine.

Implements Section 8 of docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx:
- Fixed taxonomy with strict code enforcement.
- Policies: auto, auto+log, always_ask, never_fill.
- Sensitive credentials/IDs are never filled (no exceptions).
- Unknown/unclassified fields default to always_ask (fail closed).
- Policy decisions are enforced in Python code, not LLM prompts.
- LLM outputs can never override security rules or safety policies.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from worker.answers.exceptions import PolicyViolationError
from worker.policy.taxonomy import (
    CATEGORY_KEYWORD_RULES,
    DEFAULT_CATEGORY_POLICIES,
    FieldCategory,
    PolicyType,
    SENSITIVE_SECURITY_KEYWORDS,
)

logger = logging.getLogger("worker.policy.engine")


@dataclass(frozen=True)
class PolicyDecision:
    """Immutable audit record of a code-enforced policy evaluation."""

    field_key: str
    category: FieldCategory
    policy: PolicyType
    allowed: bool
    requires_logging: bool
    requires_user_approval: bool
    is_blocked: bool
    reason: str

    def to_audit_dict(self) -> Dict[str, Any]:
        """Return structured, sanitized audit metadata."""
        return {
            "field_key": self.field_key,
            "category": self.category.value,
            "policy": self.policy.value,
            "allowed": self.allowed,
            "requires_logging": self.requires_logging,
            "requires_user_approval": self.requires_user_approval,
            "is_blocked": self.is_blocked,
            "reason": self.reason,
        }


class PolicyEngine:
    """Code-enforced policy engine governing form field filling."""

    def __init__(self, custom_category_policies: Optional[Dict[FieldCategory, PolicyType]] = None) -> None:
        self._category_policies = dict(DEFAULT_CATEGORY_POLICIES)
        if custom_category_policies:
            # Sensitive security can NEVER be overridden from never_fill
            for cat, pol in custom_category_policies.items():
                if cat == FieldCategory.SENSITIVE_SECURITY and pol != PolicyType.NEVER_FILL:
                    raise PolicyViolationError(
                        "Cannot override SENSITIVE_SECURITY category: must strictly remain never_fill."
                    )
                self._category_policies[cat] = pol

    def classify_field(self, field_key: str, label_text: Optional[str] = None) -> FieldCategory:
        """Deterministically classify a form field into the fixed taxonomy.

        Rules:
        1. Check for sensitive security keywords first (fail closed).
        2. Match deterministic keywords in normalized key and label.
        3. Default to UNKNOWN_UNCLASSIFIED if ambiguous or unrecognized.
        """
        combined = f"{field_key} {label_text or ''}".lower()
        normalized_combined = re.sub(r"[^a-z0-9_ ]+", " ", combined)

        # 1. Immediate sensitive security check: strictly never automate
        for kw in SENSITIVE_SECURITY_KEYWORDS:
            if kw in combined or kw in normalized_combined:
                return FieldCategory.SENSITIVE_SECURITY

        # 2. Check each taxonomy category's keyword rules
        # Order matters: check explicit categories before generic ones
        for category, keywords in CATEGORY_KEYWORD_RULES.items():
            if category == FieldCategory.SENSITIVE_SECURITY:
                continue
            for kw in keywords:
                # Word boundary or underscore match to avoid false positive substring matches
                pattern = rf"(^|[\s_]){re.escape(kw)}([\s_]|$)"
                if re.search(pattern, normalized_combined):
                    return category

        return FieldCategory.UNKNOWN_UNCLASSIFIED

    def evaluate(
        self,
        field_key: str,
        label_text: Optional[str] = None,
        explicit_policy: Optional[str] = None,
        category_hint: Optional[str] = None,
    ) -> PolicyDecision:
        """Evaluate and enforce policy for a target field.

        Args:
            field_key: Unique identifier or name of the field.
            label_text: Optional human-readable label from the form.
            explicit_policy: Optional policy string configured on an Answer Bank record.
            category_hint: Optional category hint from external classification.

        Returns:
            PolicyDecision: Immutable decision indicating whether filling is allowed.
        """
        if not field_key or not field_key.strip():
            return PolicyDecision(
                field_key="",
                category=FieldCategory.UNKNOWN_UNCLASSIFIED,
                policy=PolicyType.ALWAYS_ASK,
                allowed=False,
                requires_logging=False,
                requires_user_approval=True,
                is_blocked=False,
                reason="Field key is empty or whitespace; failing closed to always_ask.",
            )

        clean_key = field_key.strip()
        category = self.classify_field(clean_key, label_text)

        # If deterministic classification was unknown, verify if category_hint is a valid taxonomy category
        if category == FieldCategory.UNKNOWN_UNCLASSIFIED and category_hint:
            try:
                hint_cat = FieldCategory(category_hint.lower())
                # An external hint can never downgrade sensitive security
                if hint_cat != FieldCategory.SENSITIVE_SECURITY:
                    category = hint_cat
            except ValueError:
                # Invalid hint; remain UNKNOWN_UNCLASSIFIED
                category = FieldCategory.UNKNOWN_UNCLASSIFIED

        # 1. SENSITIVE_SECURITY is strictly never_fill. No overrides permitted.
        if category == FieldCategory.SENSITIVE_SECURITY:
            return PolicyDecision(
                field_key=clean_key,
                category=FieldCategory.SENSITIVE_SECURITY,
                policy=PolicyType.NEVER_FILL,
                allowed=False,
                requires_logging=False,
                requires_user_approval=False,
                is_blocked=True,
                reason="Classified as SENSITIVE_SECURITY: automation strictly prohibited.",
            )

        # 2. Determine base policy from taxonomy
        base_policy = self._category_policies.get(category, PolicyType.ALWAYS_ASK)

        # 3. Handle explicit policy from AnswerBank entry if provided
        final_policy = base_policy
        if explicit_policy:
            try:
                parsed_policy = PolicyType(explicit_policy.lower())
                # An explicit policy can tighten restrictions (e.g. from auto to always_ask),
                # but cannot loosen sensitive security or legal consent restrictions.
                if category in (FieldCategory.CRIMINAL_AND_HEALTH, FieldCategory.LEGAL_CONSENTS):
                    if parsed_policy in (PolicyType.AUTO, PolicyType.AUTO_LOG):
                        logger.warning(
                            "Cannot loosen policy for sensitive category %s; enforcing %s",
                            category.value,
                            base_policy.value,
                        )
                        final_policy = base_policy
                    else:
                        final_policy = parsed_policy
                else:
                    final_policy = parsed_policy
            except ValueError:
                logger.warning(
                    "Invalid explicit policy '%s' provided for field '%s'; failing closed to always_ask",
                    explicit_policy,
                    clean_key,
                )
                final_policy = PolicyType.ALWAYS_ASK

        # Compute decision flags
        allowed = final_policy in (PolicyType.AUTO, PolicyType.AUTO_LOG)
        requires_logging = final_policy == PolicyType.AUTO_LOG
        requires_user_approval = final_policy == PolicyType.ALWAYS_ASK
        is_blocked = final_policy == PolicyType.NEVER_FILL

        reason = f"Field classified as '{category.value}' with policy '{final_policy.value}'."
        if requires_user_approval:
            reason += " User review/approval is mandatory before populating."
        elif is_blocked:
            reason += " Field is blocked from automatic population."

        return PolicyDecision(
            field_key=clean_key,
            category=category,
            policy=final_policy,
            allowed=allowed,
            requires_logging=requires_logging,
            requires_user_approval=requires_user_approval,
            is_blocked=is_blocked,
            reason=reason,
        )
