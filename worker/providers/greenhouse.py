"""Greenhouse job application form provider adapter."""

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from worker.answers.models import ResolutionStatus
from worker.answers.resolver import AnswerResolver
from worker.core.exceptions import RealSubmitGateBlockedError
from worker.policy.engine import PolicyEngine
from worker.policy.taxonomy import PolicyType
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

        # 1. First Name
        if "first_name" in clean_id or "first name" in clean_label:
            name_parts = profile.candidate.name.split()
            return name_parts[0] if name_parts else profile.candidate.name

        # 2. Last Name
        if "last_name" in clean_id or "last name" in clean_label:
            name_parts = profile.candidate.name.split()
            return " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        # 3. Email
        if "email" in clean_id or "email" in clean_label:
            return profile.candidate.email

        # 4. Phone
        if "phone" in clean_id or "phone" in clean_label:
            return profile.candidate.phone or None

        # 5. LinkedIn Profile
        if "linkedin" in clean_label or "linkedin" in clean_id:
            return profile.candidate.links.get("linkedin")

        # 6. Website / Portfolio
        if "website" in clean_label or "portfolio" in clean_label:
            return profile.candidate.links.get("portfolio") or profile.candidate.links.get("website")

        # 7. GitHub Profile
        if "github" in clean_label:
            return profile.candidate.links.get("github")

        # Any unclassified or custom question fails closed: do NOT invent candidate facts
        return None

    async def inspect_and_fill(
        self,
        page: Any,
        profile: ProfileSnapshot,
        dry_run: bool = True,
        screenshot_dir: Optional[Path] = None,
    ) -> FormFillResult:
        """Inspect and fill a Greenhouse form in dry-run mode.

        CRITICAL SAFETY RULES:
        - Real submission is strictly prohibited in this phase.
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

        try:
            # Query all interactive form fields within the application form
            inputs = await page.query_selector_all("form input, form textarea")

            for element in inputs:
                input_type = (await element.get_attribute("type") or "text").strip().lower()
                # 1. Skip sensitive input types immediately before reading labels or data
                if input_type in SENSITIVE_INPUT_TYPES:
                    continue

                field_id = (await element.get_attribute("id") or "").strip()
                field_name = (await element.get_attribute("name") or "").strip()
                aria_label = (await element.get_attribute("aria-label") or "").strip()
                class_attr = (await element.get_attribute("class") or "").strip()

                # Extract associated label
                label_text = ""
                if field_id:
                    label_el = await page.query_selector(f"label[for='{field_id}']")
                    if label_el:
                        label_text = await label_el.inner_text()

                if not label_text and field_name:
                    label_text = field_name

                identifier = label_text.strip() or field_id or field_name

                # 2. Skip explicitly classified sensitive fields (OTP, CAPTCHA, passwords, government IDs)
                combined_descriptor = f"{field_id} {field_name} {aria_label} {class_attr} {label_text}".lower()
                if any(kw in combined_descriptor for kw in SENSITIVE_SECURITY_KEYWORDS):
                    continue

                resolved_value = self.resolve_field(identifier, field_id, profile)

                if resolved_value is not None:
                    # Fill field using Playwright
                    await element.fill(resolved_value)
                    fields_filled[identifier] = resolved_value
                else:
                    # Field could not be truthfully answered from candidate profile
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
                screenshot_path=None,
                submit_attempted=False,
                success=False,
                error_message=str(exc),
            )
