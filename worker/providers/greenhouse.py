"""Greenhouse job application form provider adapter and parser foundation.

Following Architecture v1.0 LOCKED and Phase 1.1 Requirements:
- Inspects application forms and extracts normalized FormField metadata.
- Connects fields to AnswerResolver, PolicyEngine, and ProfileSnapshot.
- Unknown/ambiguous fields remain unresolved (fail closed).
- Sensitive fields remain NEVER_FILL and are blocked from automation.
- Policy approval is mandatory: matching answers alone do not authorize filling.
- Supports both Playwright browser inspection and static HTML fixture parsing.
- Strictly dry-run: never clicks submit or executes live applications.
"""

from html.parser import HTMLParser
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

logger = logging.getLogger("worker.providers.greenhouse")

# Input types that must NEVER be populated or submitted during dry-run
SENSITIVE_INPUT_TYPES = {
    "submit",
    "button",
    "hidden",
    "file",
    "password",
    "image",
    "reset",
}

# Substrings identifying classified sensitive security/credential/identity fields
SENSITIVE_SECURITY_KEYWORDS = (
    "captcha",
    "recaptcha",
    "hcaptcha",
    "turnstile",
    "otp",
    "one-time",
    "verification_code",
    "security_code",
    "mfa",
    "2fa",
    "password",
    "ssn",
    "social_security",
    "national_id",
    "passport",
    "bank",
    "routing_number",
    "credit_card",
)


class GreenhouseHTMLFormParser(HTMLParser):
    """Deterministic HTML parser extracting form fields and associated labels from HTML fixtures."""

    def __init__(self) -> None:
        super().__init__()
        self.fields: List[Dict[str, Any]] = []
        self._labels_by_for: Dict[str, str] = {}
        self._current_label_for: Optional[str] = None
        self._current_label_text: List[str] = []
        self._current_select: Optional[Dict[str, Any]] = None
        self._current_option_text: List[str] = []
        self._in_option = False

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag == "label":
            self._current_label_for = attrs_dict.get("for")
            self._current_label_text = []

        elif tag == "input":
            input_type = attrs_dict.get("type", "text").strip().lower()
            field_id = attrs_dict.get("id", "").strip()
            field_name = attrs_dict.get("name", "").strip()
            aria_label = attrs_dict.get("aria-label", "").strip()
            required = "required" in attrs_dict or attrs_dict.get("aria-required") == "true"

            self.fields.append({
                "field_id": field_id,
                "name": field_name,
                "field_type": input_type,
                "required": required,
                "aria_label": aria_label,
                "options": [],
                "tag": "input",
            })

        elif tag == "textarea":
            field_id = attrs_dict.get("id", "").strip()
            field_name = attrs_dict.get("name", "").strip()
            aria_label = attrs_dict.get("aria-label", "").strip()
            required = "required" in attrs_dict or attrs_dict.get("aria-required") == "true"

            self.fields.append({
                "field_id": field_id,
                "name": field_name,
                "field_type": "textarea",
                "required": required,
                "aria_label": aria_label,
                "options": [],
                "tag": "textarea",
            })

        elif tag == "select":
            field_id = attrs_dict.get("id", "").strip()
            field_name = attrs_dict.get("name", "").strip()
            aria_label = attrs_dict.get("aria-label", "").strip()
            required = "required" in attrs_dict or attrs_dict.get("aria-required") == "true"

            self._current_select = {
                "field_id": field_id,
                "name": field_name,
                "field_type": "select",
                "required": required,
                "aria_label": aria_label,
                "options": [],
                "tag": "select",
            }
            self.fields.append(self._current_select)

        elif tag == "option" and self._current_select is not None:
            self._in_option = True
            self._current_option_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "label":
            if self._current_label_for:
                label_text = "".join(self._current_label_text).strip()
                self._labels_by_for[self._current_label_for] = label_text
            self._current_label_for = None
            self._current_label_text = []

        elif tag == "select":
            self._current_select = None

        elif tag == "option" and self._in_option:
            self._in_option = False
            opt_text = "".join(self._current_option_text).strip()
            if self._current_select is not None and opt_text:
                self._current_select["options"].append(opt_text)
            self._current_option_text = []

    def handle_data(self, data: str) -> None:
        if self._current_label_for is not None:
            self._current_label_text.append(data)
        if self._in_option:
            self._current_option_text.append(data)


def parse_greenhouse_form_html(
    html_content: str,
    profile: Optional[ProfileSnapshot] = None,
    answer_resolver: Optional[AnswerResolver] = None,
    policy_engine: Optional[PolicyEngine] = None,
    scope: str = "provider:greenhouse",
) -> List[FormField]:
    """Parse a Greenhouse HTML form fixture into strongly typed normalized FormField objects.

    Extracts:
    - field_id, name, label, field_type, required flag, options
    - PolicyEngine taxonomy classification and policy
    - ResolutionStatus from AnswerResolver or profile
    - Mandatory policy approval verification
    """
    engine = policy_engine or PolicyEngine()
    parser = GreenhouseHTMLFormParser()
    parser.feed(html_content)

    discovered: List[FormField] = []

    for raw in parser.fields:
        field_id = raw["field_id"]
        field_name = raw["name"]
        field_type = raw["field_type"]
        is_required = raw["required"]
        options = raw["options"]

        # Resolve associated label
        label_text = ""
        if field_id in parser._labels_by_for:
            label_text = parser._labels_by_for[field_id]
        if not label_text and raw["aria_label"]:
            label_text = raw["aria_label"]
        if not label_text and field_name:
            label_text = field_name
        if not label_text:
            label_text = field_id or "unlabeled_field"

        # Check required indicator in label text (e.g. '*')
        if "*" in label_text:
            is_required = True

        clean_label = label_text.replace("*", "").strip()
        primary_key = field_id.strip().lower() or clean_label.lower()

        # Check for sensitive input type or classified credentials
        is_sensitive_type = field_type in SENSITIVE_INPUT_TYPES
        combined_descriptor = f"{field_id} {field_name} {clean_label}".lower()
        is_sensitive_kw = any(kw in combined_descriptor for kw in SENSITIVE_SECURITY_KEYWORDS)

        # Policy evaluation
        decision = engine.evaluate(primary_key, clean_label)

        if is_sensitive_type or is_sensitive_kw or decision.is_blocked:
            # Sensitive fields strictly fail closed
            form_field = FormField(
                field_id=field_id or str(uuid.uuid4()),
                name=field_name or None,
                label=clean_label,
                field_type=field_type,
                required=is_required,
                options=options,
                classification=FieldCategory.SENSITIVE_SECURITY,
                policy=PolicyType.NEVER_FILL,
                resolution_status=ResolutionStatus.POLICY_BLOCKED,
                resolved_value=None,
                applied_option=None,
                is_resolved=False,
                policy_approved=False,
                reason="Sensitive credential, password, or security field blocked from automated filling",
                audit_metadata={"security_gate": "NEVER_FILL_BLOCKED"},
            )
            discovered.append(form_field)
            continue

        # Non-sensitive: attempt resolution through AnswerResolver or Profile
        resolved_value: Optional[Any] = None
        applied_option: Optional[str] = None
        resolution_status = ResolutionStatus.NO_MATCH
        policy_approved = False
        final_policy = decision.policy
        reason = ""
        audit_metadata: Dict[str, Any] = {}

        if answer_resolver is not None and profile is not None:
            res = answer_resolver.resolve_with_profile_fallback(
                field_key=primary_key,
                label_text=clean_label,
                profile=profile,
                scope=scope,
            )
            resolution_status = res.status
            resolved_value = res.resolved_value
            applied_option = res.applied_option
            final_policy = res.policy
            policy_approved = res.policy_approved
            reason = res.reason
            audit_metadata = res.audit_metadata

        elif profile is not None:
            # Fallback direct profile resolution respecting PolicyEngine
            val = _resolve_profile_field(primary_key, clean_label, profile)
            if val is not None:
                resolved_value = val
                policy_approved = decision.allowed and not decision.requires_user_approval
                if policy_approved:
                    resolution_status = ResolutionStatus.RESOLVED
                    reason = "Resolved directly from verified candidate profile with policy approval"
                else:
                    resolution_status = ResolutionStatus.NEEDS_USER_INPUT
                    reason = f"Candidate fact resolved but policy '{decision.policy.value}' requires explicit user approval"
            else:
                resolution_status = ResolutionStatus.NEEDS_USER_INPUT if is_required else ResolutionStatus.NO_MATCH
                reason = "No verified candidate fact found in profile"

        else:
            # No profile provided
            resolution_status = ResolutionStatus.NEEDS_USER_INPUT if is_required else ResolutionStatus.NO_MATCH
            reason = "No candidate profile supplied for resolution"

        form_field = FormField(
            field_id=field_id or str(uuid.uuid4()),
            name=field_name or None,
            label=clean_label,
            field_type=field_type,
            required=is_required,
            options=options,
            classification=decision.category,
            policy=final_policy,
            resolution_status=resolution_status,
            resolved_value=resolved_value,
            applied_option=applied_option,
            is_resolved=(resolution_status == ResolutionStatus.RESOLVED and resolved_value is not None),
            policy_approved=policy_approved,
            reason=reason,
            audit_metadata=audit_metadata,
        )
        discovered.append(form_field)

    return discovered


def _resolve_profile_field(clean_id: str, clean_label: str, profile: ProfileSnapshot) -> Optional[str]:
    """Helper to resolve standard candidate facts from ProfileSnapshot."""
    clean_id = clean_id.lower()
    clean_label = clean_label.lower()

    if "first_name" in clean_id or "first name" in clean_label:
        parts = profile.candidate.name.split()
        return parts[0] if parts else profile.candidate.name

    if "last_name" in clean_id or "last name" in clean_label:
        parts = profile.candidate.name.split()
        return " ".join(parts[1:]) if len(parts) > 1 else ""

    if "email" in clean_id or "email" in clean_label:
        return profile.candidate.email

    if "phone" in clean_id or "phone" in clean_label:
        return profile.candidate.phone or None

    if "linkedin" in clean_label or "linkedin" in clean_id:
        return profile.candidate.links.get("linkedin")

    if "website" in clean_label or "portfolio" in clean_label:
        return profile.candidate.links.get("portfolio") or profile.candidate.links.get("website")

    if "github" in clean_label or "github" in clean_id:
        return profile.candidate.links.get("github")

    return None


class GreenhouseProvider(JobProvider):
    """Greenhouse job application adapter enforcing dry-run inspection and truthfulness."""

    name: str = "greenhouse"

    def __init__(
        self,
        answer_resolver: Optional[AnswerResolver] = None,
        policy_engine: Optional[PolicyEngine] = None,
    ) -> None:
        self.answer_resolver = answer_resolver
        self.policy_engine = policy_engine or PolicyEngine()

    def resolve_field(
        self,
        label_text: str,
        field_id: str,
        profile: ProfileSnapshot,
        scope: str = "provider:greenhouse",
    ) -> Optional[str]:
        """Resolve a field value strictly through Answer Bank and PolicyEngine without inventing answers.

        Returns:
            Resolved string value if a verified fact exists and is policy approved; None otherwise.
        """
        clean_label = label_text.strip().lower()
        clean_id = field_id.strip().lower()
        primary_key = clean_id or clean_label

        # 1. If AnswerResolver is injected, resolve with Answer Bank and Profile fallback
        if self.answer_resolver is not None:
            res = self.answer_resolver.resolve_with_profile_fallback(
                field_key=primary_key,
                label_text=label_text,
                profile=profile,
                scope=scope,
            )
            if res.status == ResolutionStatus.RESOLVED and res.policy_approved:
                return str(res.resolved_value)
            return None

        # 2. Otherwise enforce PolicyEngine over candidate profile
        decision = self.policy_engine.evaluate(primary_key, label_text)
        if not decision.allowed or decision.is_blocked:
            return None
        if not (decision.allowed and not decision.requires_user_approval):
            return None

        return _resolve_profile_field(clean_id, clean_label, profile)

    async def inspect_and_fill(
        self,
        page: Any,
        profile: ProfileSnapshot,
        dry_run: bool = True,
        screenshot_dir: Optional[Path] = None,
    ) -> FormFillResult:
        """Inspect and fill a Greenhouse form in dry-run mode.

        CRITICAL SAFETY RULES:
        - Real submission is strictly prohibited.
        - Never click the submit button.
        - Never upload resumes or populate credentials/passwords.
        - Skip sensitive fields (OTP, CAPTCHA, passwords) before resolving candidate values.
        - Never invent candidate facts for unknown or ambiguous fields.
        """
        if not dry_run:
            raise RealSubmitGateBlockedError(
                "Greenhouse provider cannot execute real submissions: Real-Submit Gate is locked."
            )

        fields_filled: Dict[str, str] = {}
        unresolved_fields: List[str] = []
        discovered_fields: List[FormField] = []

        try:
            # Query all interactive form fields within the application form
            inputs = await page.query_selector_all("form input, form textarea, form select")

            for element in inputs:
                input_type = (await element.get_attribute("type") or "text").strip().lower()
                field_id = (await element.get_attribute("id") or "").strip()
                field_name = (await element.get_attribute("name") or "").strip()
                aria_label = (await element.get_attribute("aria-label") or "").strip()
                class_attr = (await element.get_attribute("class") or "").strip()
                required_attr = await element.get_attribute("required")
                aria_required = await element.get_attribute("aria-required")
                is_required = required_attr is not None or aria_required == "true"

                # Extract associated label
                label_text = ""
                if field_id:
                    label_el = await page.query_selector(f"label[for='{field_id}']")
                    if label_el:
                        label_text = await label_el.inner_text()

                if not label_text and field_name:
                    label_text = field_name

                identifier = label_text.strip() or field_id or field_name
                clean_label = label_text.replace("*", "").strip() or identifier
                primary_key = field_id.strip().lower() or clean_label.lower()

                # Extract options for select elements
                options: List[str] = []
                tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                if tag_name == "select":
                    input_type = "select"
                    option_elements = await element.query_selector_all("option")
                    for opt in option_elements:
                        opt_text = (await opt.inner_text()).strip()
                        if opt_text:
                            options.append(opt_text)
                elif tag_name == "textarea":
                    input_type = "textarea"

                # Evaluate classification and policy
                decision = self.policy_engine.evaluate(primary_key, clean_label)

                # Check sensitive input types or security keywords
                combined_descriptor = f"{field_id} {field_name} {aria_label} {class_attr} {label_text}".lower()
                is_sensitive_type = input_type in SENSITIVE_INPUT_TYPES
                is_sensitive_kw = any(kw in combined_descriptor for kw in SENSITIVE_SECURITY_KEYWORDS)

                if is_sensitive_type or is_sensitive_kw or decision.is_blocked:
                    form_field = FormField(
                        field_id=field_id or str(uuid.uuid4()),
                        name=field_name or None,
                        label=clean_label,
                        field_type=input_type,
                        required=is_required,
                        options=options,
                        classification=FieldCategory.SENSITIVE_SECURITY,
                        policy=PolicyType.NEVER_FILL,
                        resolution_status=ResolutionStatus.POLICY_BLOCKED,
                        resolved_value=None,
                        applied_option=None,
                        is_resolved=False,
                        policy_approved=False,
                        reason="Sensitive credential or security question blocked from automation",
                    )
                    discovered_fields.append(form_field)
                    continue

                # Resolve field
                resolved_value: Optional[Any] = None
                policy_approved = False
                resolution_status = ResolutionStatus.NO_MATCH
                final_policy = decision.policy
                reason = ""
                audit_meta: Dict[str, Any] = {}

                if self.answer_resolver is not None:
                    res = self.answer_resolver.resolve_with_profile_fallback(
                        field_key=primary_key,
                        label_text=clean_label,
                        profile=profile,
                        scope="provider:greenhouse",
                    )
                    resolution_status = res.status
                    resolved_value = res.resolved_value
                    final_policy = res.policy
                    policy_approved = res.policy_approved
                    reason = res.reason
                    audit_meta = res.audit_metadata
                else:
                    val = _resolve_profile_field(field_id, clean_label, profile)
                    if val is not None:
                        resolved_value = val
                        policy_approved = decision.allowed and not decision.requires_user_approval
                        if policy_approved:
                            resolution_status = ResolutionStatus.RESOLVED
                            reason = "Resolved directly from candidate profile with policy approval"
                        else:
                            resolution_status = ResolutionStatus.NEEDS_USER_INPUT
                            reason = f"Resolved from profile but policy '{decision.policy.value}' requires approval"
                    else:
                        resolution_status = ResolutionStatus.NEEDS_USER_INPUT if is_required else ResolutionStatus.NO_MATCH
                        reason = "Unknown field cannot be resolved from candidate profile"

                is_resolved = (resolution_status == ResolutionStatus.RESOLVED and resolved_value is not None)

                form_field = FormField(
                    field_id=field_id or str(uuid.uuid4()),
                    name=field_name or None,
                    label=clean_label,
                    field_type=input_type,
                    required=is_required,
                    options=options,
                    classification=decision.category,
                    policy=final_policy,
                    resolution_status=resolution_status,
                    resolved_value=resolved_value,
                    is_resolved=is_resolved,
                    policy_approved=policy_approved,
                    reason=reason,
                    audit_metadata=audit_meta,
                )
                discovered_fields.append(form_field)

                # Fill field ONLY if resolved AND policy approved
                if is_resolved and policy_approved:
                    val_str = str(resolved_value)
                    if tag_name == "select":
                        await element.select_option(label=val_str)
                    else:
                        await element.fill(val_str)
                    fields_filled[identifier] = val_str
                else:
                    unresolved_fields.append(identifier)

            # Capture evidence screenshot if directory is provided
            screenshot_path_str: Optional[str] = None
            if screenshot_dir:
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                shot_file = screenshot_dir / f"greenhouse_dryrun_{uuid.uuid4().hex[:8]}.png"
                await page.screenshot(path=str(shot_file), full_page=True)
                screenshot_path_str = str(shot_file)

            return FormFillResult(
                provider=self.name,
                fields_filled=fields_filled,
                unresolved_fields=unresolved_fields,
                discovered_fields=discovered_fields,
                screenshot_path=screenshot_path_str,
                submit_attempted=False,
                success=True,
            )

        except Exception as exc:
            logger.exception("Error during Greenhouse form dry-run inspection")
            return FormFillResult(
                provider=self.name,
                fields_filled=fields_filled,
                unresolved_fields=unresolved_fields,
                discovered_fields=discovered_fields,
                screenshot_path=None,
                submit_attempted=False,
                success=False,
                error_message=str(exc),
            )
