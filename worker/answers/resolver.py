"""Deterministic Answer Resolution Engine.

Implements Section 7 of docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx:
Resolution order:
1. Policy pre-check (fail closed if sensitive/blocked).
2. Exact key matching (scoped, then global).
3. Normalized alias matching.
4. Matching compatible question variants.
5. Strict verification check (reject expired, unverified, or needs_review records).
6. Option mapping validation for dropdown/select fields.
7. Unresolved result (NEEDS_USER_INPUT / NO_MATCH / AMBIGUOUS) when no reliable answer exists.
"""

import logging
from datetime import datetime
from typing import Any, List, Optional, Protocol

from worker.answers.audit import build_audit_metadata
from worker.answers.models import (
    AnswerBankEntry,
    FieldResolutionResult,
    ResolutionStatus,
)
from worker.answers.repository import AnswerBankRepository, normalize_query_text
from worker.policy.engine import PolicyDecision, PolicyEngine
from worker.policy.taxonomy import PolicyType
from worker.profile.models import ProfileSnapshot

logger = logging.getLogger("worker.answers.resolver")


class AmbiguityResolutionHandler(Protocol):
    """Extension interface for future LLM-assisted or semantic ambiguity resolution.

    Ensures that any future AI ambiguity resolution remains behind a strictly typed boundary.
    """

    async def resolve_ambiguity(
        self,
        query: str,
        candidates: List[AnswerBankEntry],
        field_type: str,
    ) -> Optional[AnswerBankEntry]:
        """Attempt to resolve ambiguity among candidate answers."""
        ...


class AnswerResolver:
    """Deterministic field resolution engine with code-enforced policy gates."""

    def __init__(
        self,
        repository: AnswerBankRepository,
        policy_engine: PolicyEngine,
        ambiguity_handler: Optional[AmbiguityResolutionHandler] = None,
    ) -> None:
        self.repository = repository
        self.policy_engine = policy_engine
        self.ambiguity_handler = ambiguity_handler

    def resolve_field(
        self,
        field_key: str,
        label_text: Optional[str] = None,
        scope: str = "global",
        available_options: Optional[List[str]] = None,
        as_of: Optional[datetime] = None,
    ) -> FieldResolutionResult:
        """Deterministically resolve a form field using Answer Bank and PolicyEngine.

        Args:
            field_key: Identifier/name of the form field.
            label_text: Optional human-readable label from the form.
            scope: Application scope (e.g. 'company:google', 'provider:greenhouse', or 'global').
            available_options: Optional list of available options for dropdown/radio fields.
            as_of: Reference time for validity checks (default UTC now).

        Returns:
            FieldResolutionResult: Typed resolution result with audit metadata.
        """
        clean_key = field_key.strip().lower()
        search_query = label_text.strip() if label_text and label_text.strip() else clean_key

        # 0. Policy Pre-Check
        policy_decision = self.policy_engine.evaluate(
            field_key=clean_key,
            label_text=label_text,
        )

        if policy_decision.is_blocked:
            audit = build_audit_metadata(
                field_key=clean_key,
                resolution_method="policy_pre_check",
                policy_applied=policy_decision.policy.value,
                result_status=ResolutionStatus.POLICY_BLOCKED.value,
                reason=policy_decision.reason,
            )
            return FieldResolutionResult(
                status=ResolutionStatus.POLICY_BLOCKED,
                field_key=clean_key,
                resolved_value=None,
                policy=PolicyType.NEVER_FILL,
                policy_approved=False,
                reason=policy_decision.reason,
                audit_metadata=audit,
            )

        # 1. Exact Key Matching (Scope hierarchy: specific scope -> global)
        entry: Optional[AnswerBankEntry] = self.repository.get(clean_key, scope=scope)
        resolution_method = "exact_key"

        if entry is None and scope != "global":
            entry = self.repository.get(clean_key, scope="global")
            if entry is not None:
                resolution_method = "exact_key_global_fallback"

        # 2 & 3. Normalized Alias & Variant Matching
        if entry is None:
            alias_matches = self.repository.search_by_alias(search_query, scope=scope)
            if not alias_matches and scope != "global":
                alias_matches = self.repository.search_by_alias(search_query, scope="global")

            if len(alias_matches) == 1:
                entry = alias_matches[0]
                resolution_method = "alias_or_variant_match"
            elif len(alias_matches) > 1:
                # Check if all matches have identical values
                distinct_values = {str(m.value) for m in alias_matches}
                if len(distinct_values) == 1:
                    entry = alias_matches[0]
                    resolution_method = "alias_concordant_match"
                else:
                    audit = build_audit_metadata(
                        field_key=clean_key,
                        resolution_method="alias_search",
                        policy_applied=policy_decision.policy.value,
                        result_status=ResolutionStatus.AMBIGUOUS.value,
                        reason=f"Multiple conflicting answers ({len(alias_matches)}) match query '{search_query}'.",
                    )
                    return FieldResolutionResult(
                        status=ResolutionStatus.AMBIGUOUS,
                        field_key=clean_key,
                        resolved_value=None,
                        policy=policy_decision.policy,
                        policy_approved=False,
                        reason=f"Ambiguous match: multiple distinct answers found for query '{search_query}'.",
                        audit_metadata=audit,
                    )

        # 4. Handle No Match
        if entry is None:
            audit = build_audit_metadata(
                field_key=clean_key,
                resolution_method="none",
                policy_applied=policy_decision.policy.value,
                result_status=ResolutionStatus.NO_MATCH.value,
                reason="No matching entry found in Answer Bank.",
            )
            return FieldResolutionResult(
                status=ResolutionStatus.NO_MATCH,
                field_key=clean_key,
                resolved_value=None,
                policy=policy_decision.policy,
                policy_approved=False,
                reason="No verified answer exists in Answer Bank for this question.",
                audit_metadata=audit,
            )

        # 5. Validity, Expiration and Verification Checks
        if entry.is_expired(as_of):
            audit = build_audit_metadata(
                field_key=clean_key,
                resolution_method=resolution_method,
                policy_applied=policy_decision.policy.value,
                result_status=ResolutionStatus.EXPIRED.value,
                reason=f"Answer expired on {entry.valid_until.isoformat() if entry.valid_until else 'unknown'}.",
                source=entry.source.value,
                entry_key=entry.key,
                raw_value=entry.value,
            )
            return FieldResolutionResult(
                status=ResolutionStatus.EXPIRED,
                field_key=clean_key,
                resolved_value=None,
                entry=entry,
                policy=policy_decision.policy,
                policy_approved=False,
                reason="Answer record is expired past valid_until date; user confirmation required.",
                audit_metadata=audit,
            )

        if entry.needs_review:
            audit = build_audit_metadata(
                field_key=clean_key,
                resolution_method=resolution_method,
                policy_applied=policy_decision.policy.value,
                result_status=ResolutionStatus.NEEDS_USER_INPUT.value,
                reason="Answer record is flagged with needs_review=True.",
                source=entry.source.value,
                entry_key=entry.key,
                raw_value=entry.value,
            )
            return FieldResolutionResult(
                status=ResolutionStatus.NEEDS_USER_INPUT,
                field_key=clean_key,
                resolved_value=None,
                entry=entry,
                policy=policy_decision.policy,
                policy_approved=False,
                reason="Answer record is unverified or flagged for user review.",
                audit_metadata=audit,
            )

        # 6. Re-evaluate Policy with Entry Policy
        final_policy_decision = self.policy_engine.evaluate(
            field_key=clean_key,
            label_text=label_text,
            explicit_policy=entry.policy.value,
            category_hint=entry.category,
        )

        if final_policy_decision.is_blocked:
            audit = build_audit_metadata(
                field_key=clean_key,
                resolution_method=resolution_method,
                policy_applied=final_policy_decision.policy.value,
                result_status=ResolutionStatus.POLICY_BLOCKED.value,
                reason=final_policy_decision.reason,
                source=entry.source.value,
                entry_key=entry.key,
                raw_value=entry.value,
            )
            return FieldResolutionResult(
                status=ResolutionStatus.POLICY_BLOCKED,
                field_key=clean_key,
                resolved_value=None,
                entry=entry,
                policy=final_policy_decision.policy,
                policy_approved=False,
                reason=final_policy_decision.reason,
                audit_metadata=audit,
            )

        # If policy is ALWAYS_ASK, user approval is required even if answer exists
        if final_policy_decision.requires_user_approval:
            audit = build_audit_metadata(
                field_key=clean_key,
                resolution_method=resolution_method,
                policy_applied=final_policy_decision.policy.value,
                result_status=ResolutionStatus.NEEDS_USER_INPUT.value,
                reason="Policy requires explicit user confirmation (always_ask).",
                source=entry.source.value,
                entry_key=entry.key,
                raw_value=entry.value,
            )
            return FieldResolutionResult(
                status=ResolutionStatus.NEEDS_USER_INPUT,
                field_key=clean_key,
                resolved_value=entry.value,
                entry=entry,
                policy=PolicyType.ALWAYS_ASK,
                policy_approved=False,
                reason="Answer found, but policy strictly requires explicit user approval (always_ask).",
                audit_metadata=audit,
            )

        # 7. Option Mapping for dropdown/radio fields
        final_value = entry.value
        applied_option: Optional[str] = None

        if available_options:
            str_val = str(entry.value).strip()
            # Check explicit option mapping first
            if entry.option_mapping:
                mapped = entry.option_mapping.get(str_val)
                # If exact key not found and value is numeric, evaluate range expressions (e.g. "<=15", "<=30")
                if not mapped:
                    try:
                        num_val = float(entry.value)
                        for pattern, opt in entry.option_mapping.items():
                            p = pattern.strip()
                            if p.startswith("<="):
                                if num_val <= float(p[2:].strip()):
                                    mapped = opt
                                    break
                            elif p.startswith(">="):
                                if num_val >= float(p[2:].strip()):
                                    mapped = opt
                                    break
                            elif p.startswith("<"):
                                if num_val < float(p[1:].strip()):
                                    mapped = opt
                                    break
                            elif p.startswith(">"):
                                if num_val > float(p[1:].strip()):
                                    mapped = opt
                                    break
                    except (ValueError, TypeError):
                        pass

                if mapped:
                    # Find exact or case-insensitive match in available_options
                    matched_opt = next(
                        (opt for opt in available_options if opt.strip().lower() == mapped.strip().lower()),
                        None,
                    )
                    if matched_opt:
                        applied_option = matched_opt
                        final_value = matched_opt
                    else:
                        audit = build_audit_metadata(
                            field_key=clean_key,
                            resolution_method=resolution_method,
                            policy_applied=final_policy_decision.policy.value,
                            result_status=ResolutionStatus.NEEDS_USER_INPUT.value,
                            reason=f"Mapped option '{mapped}' not found in available options {available_options}.",
                            source=entry.source.value,
                            entry_key=entry.key,
                            raw_value=entry.value,
                        )
                        return FieldResolutionResult(
                            status=ResolutionStatus.NEEDS_USER_INPUT,
                            field_key=clean_key,
                            resolved_value=None,
                            entry=entry,
                            policy=final_policy_decision.policy,
                            policy_approved=False,
                            reason=f"Option mapping target '{mapped}' not present in form options.",
                            audit_metadata=audit,
                        )
                else:
                    # No mapping key matched
                    audit = build_audit_metadata(
                        field_key=clean_key,
                        resolution_method=resolution_method,
                        policy_applied=final_policy_decision.policy.value,
                        result_status=ResolutionStatus.NEEDS_USER_INPUT.value,
                        reason=f"No option mapping for value '{str_val}' in {entry.option_mapping}.",
                        source=entry.source.value,
                        entry_key=entry.key,
                        raw_value=entry.value,
                    )
                    return FieldResolutionResult(
                        status=ResolutionStatus.NEEDS_USER_INPUT,
                        field_key=clean_key,
                        resolved_value=None,
                        entry=entry,
                        policy=final_policy_decision.policy,
                        policy_approved=False,
                        reason="No valid option mapping found for dropdown selection.",
                        audit_metadata=audit,
                    )
            else:
                # Direct match against available_options
                direct_match = next(
                    (opt for opt in available_options if opt.strip().lower() == str_val.lower()),
                    None,
                )
                if direct_match:
                    applied_option = direct_match
                    final_value = direct_match
                else:
                    audit = build_audit_metadata(
                        field_key=clean_key,
                        resolution_method=resolution_method,
                        policy_applied=final_policy_decision.policy.value,
                        result_status=ResolutionStatus.NEEDS_USER_INPUT.value,
                        reason=f"Value '{str_val}' not found in form options {available_options}.",
                        source=entry.source.value,
                        entry_key=entry.key,
                        raw_value=entry.value,
                    )
                    return FieldResolutionResult(
                        status=ResolutionStatus.NEEDS_USER_INPUT,
                        field_key=clean_key,
                        resolved_value=None,
                        entry=entry,
                        policy=final_policy_decision.policy,
                        policy_approved=False,
                        reason="Value does not match any valid dropdown option on the form.",
                        audit_metadata=audit,
                    )

        # 8. Successfully Resolved with Policy Approval
        audit = build_audit_metadata(
            field_key=clean_key,
            resolution_method=resolution_method,
            policy_applied=final_policy_decision.policy.value,
            result_status=ResolutionStatus.RESOLVED.value,
            reason=f"Successfully resolved via {resolution_method} with policy {final_policy_decision.policy.value}.",
            source=entry.source.value,
            entry_key=entry.key,
            raw_value=final_value,
        )

        return FieldResolutionResult(
            status=ResolutionStatus.RESOLVED,
            field_key=clean_key,
            resolved_value=final_value,
            applied_option=applied_option,
            entry=entry,
            policy=final_policy_decision.policy,
            policy_approved=True,
            reason="Verified answer resolved and policy approved.",
            audit_metadata=audit,
        )

    def resolve_with_profile_fallback(
        self,
        field_key: str,
        label_text: Optional[str] = None,
        profile: Optional[ProfileSnapshot] = None,
        scope: str = "global",
        available_options: Optional[List[str]] = None,
        as_of: Optional[datetime] = None,
    ) -> FieldResolutionResult:
        """Resolve field using Answer Bank first, then falling back to verified ProfileSnapshot."""
        # 1. Try Answer Bank first
        result = self.resolve_field(
            field_key=field_key,
            label_text=label_text,
            scope=scope,
            available_options=available_options,
            as_of=as_of,
        )

        if result.status == ResolutionStatus.RESOLVED:
            return result
        if result.status == ResolutionStatus.POLICY_BLOCKED:
            return result

        # 2. If NO_MATCH and ProfileSnapshot is provided, attempt verified profile extraction
        if result.status == ResolutionStatus.NO_MATCH and profile is not None:
            clean_key = field_key.strip().lower()
            clean_label = (label_text or "").strip().lower()

            # Policy check for profile extraction
            policy_decision = self.policy_engine.evaluate(clean_key, label_text)
            if policy_decision.is_blocked:
                return result

            # Profile resolution logic for identity/contact
            val: Optional[str] = None
            if "first_name" in clean_key or "first name" in clean_label:
                parts = profile.candidate.name.split()
                val = parts[0] if parts else profile.candidate.name
            elif "last_name" in clean_key or "last name" in clean_label:
                parts = profile.candidate.name.split()
                val = " ".join(parts[1:]) if len(parts) > 1 else ""
            elif "email" in clean_key or "email" in clean_label:
                val = profile.candidate.email
            elif "phone" in clean_key or "phone" in clean_label:
                val = profile.candidate.phone
            elif "linkedin" in clean_key or "linkedin" in clean_label:
                val = profile.candidate.links.get("linkedin")
            elif "github" in clean_key or "github" in clean_label:
                val = profile.candidate.links.get("github")
            elif "portfolio" in clean_key or "website" in clean_label or "portfolio" in clean_label:
                val = profile.candidate.links.get("portfolio") or profile.candidate.links.get("website")

            if val is not None:
                # If policy is ALWAYS_ASK, still require confirmation
                if policy_decision.requires_user_approval:
                    audit = build_audit_metadata(
                        field_key=clean_key,
                        resolution_method="profile_snapshot",
                        policy_applied=policy_decision.policy.value,
                        result_status=ResolutionStatus.NEEDS_USER_INPUT.value,
                        reason="Profile fact found, but policy requires user approval (always_ask).",
                        source="profile",
                        entry_key=clean_key,
                        raw_value=val,
                    )
                    return FieldResolutionResult(
                        status=ResolutionStatus.NEEDS_USER_INPUT,
                        field_key=clean_key,
                        resolved_value=val,
                        policy=PolicyType.ALWAYS_ASK,
                        policy_approved=False,
                        reason="Profile fact extracted, but policy requires explicit user confirmation.",
                        audit_metadata=audit,
                    )

                audit = build_audit_metadata(
                    field_key=clean_key,
                    resolution_method="profile_snapshot",
                    policy_applied=policy_decision.policy.value,
                    result_status=ResolutionStatus.RESOLVED.value,
                    reason="Resolved from verified profile snapshot with policy auto.",
                    source="profile",
                    entry_key=clean_key,
                    raw_value=val,
                )
                return FieldResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    field_key=clean_key,
                    resolved_value=val,
                    policy=policy_decision.policy,
                    policy_approved=True,
                    reason="Resolved directly from verified candidate ProfileSnapshot.",
                    audit_metadata=audit,
                )

        return result
