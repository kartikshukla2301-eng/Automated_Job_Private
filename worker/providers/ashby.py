"""Ashby job provider adapter, discovery, and form execution foundation (Phase 1.7).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 11, 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import uuid

from worker.answers.models import ResolutionStatus
from worker.answers.resolver import AnswerResolver
from worker.core.exceptions import RealSubmitGateBlockedError
from worker.discovery.models import Job, JobStatus, SalaryInfo
from worker.discovery.normalization import (
    compute_canonical_key,
    compute_content_hash,
    normalize_company,
    normalize_location,
    normalize_title,
    normalize_url,
)
from worker.discovery.security import is_safe_discovery_url, sanitize_job_description
from worker.policy.engine import PolicyEngine
from worker.policy.taxonomy import FieldCategory, PolicyType
from worker.profile.models import ProfileSnapshot
from worker.providers.base import FormField, FormFillResult, JobDiscoveryAdapter, JobProvider

logger = logging.getLogger("worker.providers.ashby")


class AshbyDiscoveryAdapter(JobDiscoveryAdapter):
    """Parses Ashby public job board payloads into canonical Job models."""

    def __init__(self) -> None:
        pass

    def parse_job_payload(self, raw_data: Dict[str, Any], default_company: str = "") -> Optional[Job]:
        """Convert an Ashby job dictionary into a strongly typed canonical Job."""
        external_id = str(raw_data.get("id") or "")
        title = raw_data.get("title") or ""
        company = raw_data.get("company") or default_company or ""
        url = raw_data.get("jobUrl") or raw_data.get("url") or ""

        if not external_id or not title or not url:
            logger.warning("Skipping malformed Ashby job record: missing required fields")
            return None

        # Extract company from url if not provided: https://jobs.ashbyhq.com/{company}/{id}
        if not company:
            match = re.search(r"jobs\.ashbyhq\.com/([^/]+)", url)
            if match:
                company = match.group(1).replace("-", " ").title()
            else:
                company = "Ashby Organization"

        if not is_safe_discovery_url(url):
            logger.warning("Unsafe discovery URL rejected: %s", url)
            return None

        canonical_url = normalize_url(url)
        norm_company = normalize_company(company)
        norm_title = normalize_title(title)

        location_raw = raw_data.get("locationName") or raw_data.get("location") or "Remote"
        is_remote = bool(raw_data.get("isRemote", False))
        loc_input = f"{location_raw} (Remote)" if is_remote and "remote" not in location_raw.lower() else location_raw
        norm_location, loc_bucket = normalize_location(loc_input)
        canonical_key = compute_canonical_key(norm_company, norm_title, loc_bucket)

        raw_desc = raw_data.get("descriptionHtml") or raw_data.get("description") or ""
        clean_desc = sanitize_job_description(raw_desc)
        content_hash = compute_content_hash(clean_desc, fallback_title=title)

        salary_info: Optional[SalaryInfo] = None
        comp_obj = raw_data.get("compensation")
        if isinstance(comp_obj, dict):
            summary = comp_obj.get("summary") or ""
            currency = comp_obj.get("currency") or "USD"
            salary_info = self._parse_compensation(summary, currency)
        elif isinstance(comp_obj, str):
            salary_info = self._parse_compensation(comp_obj, "USD")

        return Job(
            id=uuid.uuid4(),
            platform="ashby",
            external_id=external_id,
            url=canonical_url,
            canonical_key=canonical_key,
            company=company,
            normalized_company=norm_company,
            title=title,
            normalized_title=norm_title,
            location=norm_location,
            location_bucket=loc_bucket,
            employment_type=raw_data.get("employmentType", "FullTime"),
            experience_requirements=raw_data.get("experience_requirements"),
            salary=salary_info,
            description=clean_desc,
            content_hash=content_hash,
            status=JobStatus.DISCOVERED,
            metadata={
                "department": raw_data.get("department"),
                "isRemote": is_remote,
                "publishedAt": raw_data.get("publishedAt"),
            },
        )

    def parse_job_list(self, raw_list: List[Dict[str, Any]], default_company: str = "") -> List[Job]:
        """Parse multiple Ashby job board entries."""
        jobs: List[Job] = []
        for item in raw_list:
            parsed = self.parse_job_payload(item, default_company=default_company)
            if parsed:
                jobs.append(parsed)
        return jobs

    def _parse_compensation(self, comp_str: str, default_currency: str = "USD") -> Optional[SalaryInfo]:
        """Parse compensation summary into numeric min/max bounds."""
        if not comp_str:
            return None
        try:
            curr = "USD"
            if "$" in comp_str:
                curr = "$"
            elif "₹" in comp_str or "INR" in comp_str:
                curr = "INR"
            else:
                curr = default_currency

            # Find numbers
            clean_str = comp_str.replace(",", "")
            matches = re.findall(r"(\d+(?:\.\d+)?)", clean_str)
            if len(matches) >= 2:
                min_val = float(matches[0])
                max_val = float(matches[1])
                return SalaryInfo(
                    currency=curr,
                    min_amount=min_val,
                    max_amount=max_val,
                    interval="year",
                )
            elif len(matches) == 1:
                amt = float(matches[0])
                return SalaryInfo(
                    currency=curr,
                    min_amount=amt,
                    max_amount=amt,
                    interval="year",
                )
            return None
        except Exception:
            return None


class AshbyProvider(JobProvider):
    """Playwright-based provider for inspecting Ashby job applications.
    
    Adheres strictly to L0 dry-run safety and never mutates forms or clicks submit.
    """

    name: str = "ashby"

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
        """Inspect Ashby application form and extract form controls."""
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
                scope="provider:ashby",
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
                p = screenshot_dir / f"ashby_evidence_{uuid.uuid4().hex[:8]}.png"
                await page.screenshot(path=str(p))
                screenshot_path = str(p)
            except Exception as ss_err:
                logger.warning("Could not capture screenshot: %s", ss_err)

        return FormFillResult(
            provider="ashby",
            success=len(unresolved) == 0,
            discovered_fields=discovered,
            fields_filled=fields_filled,
            unresolved_fields=unresolved,
            screenshot_path=screenshot_path,
        )

    async def submit_application(self, page: Any) -> bool:
        """Submission is strictly disabled by non-negotiable safety invariant."""
        raise RealSubmitGateBlockedError(
            "Real submission is permanently disabled: real_submit_gate_enabled = False"
        )
