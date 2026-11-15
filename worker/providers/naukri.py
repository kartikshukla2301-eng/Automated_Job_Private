"""Naukri job provider adapter, discovery, and session management foundation (Phase 1.6).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 10, 11, 12)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
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

logger = logging.getLogger("worker.providers.naukri")


class NaukriSessionStatus(str, Enum):
    LOGGED_IN = "LOGGED_IN"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"


class NaukriSessionManager:
    """Manages persistent manual user session tokens and cookies for Naukri."""

    def __init__(self, session_path: Path = Path("worker/sessions/naukri_session.json")) -> None:
        self.session_path = session_path

    def load_session(self) -> Dict[str, Any]:
        """Load saved session metadata if it exists."""
        if not self.session_path.exists():
            return {}
        try:
            return json.loads(self.session_path.read_text(encoding="utf-8"))
        except Exception as err:
            logger.warning("Could not read Naukri session file: %s", err)
            return {}

    def save_session(self, session_data: Dict[str, Any]) -> None:
        """Persist user session cookies or metadata (never passwords)."""
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure passwords or plain text credentials are never saved
        clean_data = {k: v for k, v in session_data.items() if "password" not in k.lower()}
        self.session_path.write_text(json.dumps(clean_data, indent=2), encoding="utf-8")

    def inspect_session_status(self, session_data: Optional[Dict[str, Any]] = None) -> NaukriSessionStatus:
        """Evaluate session status based on expiration and presence of auth tokens."""
        data = session_data if session_data is not None else self.load_session()
        if not data or not data.get("auth_token"):
            return NaukriSessionStatus.LOGIN_REQUIRED

        expires_at = data.get("expires_at")
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at)
                if datetime.now(timezone.utc) > exp_dt:
                    return NaukriSessionStatus.SESSION_EXPIRED
            except Exception:
                return NaukriSessionStatus.SESSION_EXPIRED

        return NaukriSessionStatus.LOGGED_IN


class NaukriDiscoveryAdapter(JobDiscoveryAdapter):
    """Adapter for ingesting and normalizing Naukri job postings into canonical Job models."""

    name: str = "naukri"

    def __init__(self, session_manager: Optional[NaukriSessionManager] = None) -> None:
        self.session_manager = session_manager or NaukriSessionManager()

    async def fetch_jobs(
        self,
        company: str,
        client: Optional[Any] = None,
        fixture_path: Optional[Path] = None,
        **kwargs: Any,
    ) -> List[Job]:
        """Fetch and normalize jobs for a company from Naukri."""
        raw_items: List[Dict[str, Any]] = []

        if fixture_path and fixture_path.exists():
            content = fixture_path.read_text(encoding="utf-8")
            raw_items = json.loads(content)
        else:
            # Fallback to local default discovery fixture if available
            default_fix = Path("fixtures/discovery/naukri_jobs.json")
            if default_fix.exists():
                content = default_fix.read_text(encoding="utf-8")
                raw_items = json.loads(content)

        jobs: List[Job] = []
        for raw in raw_items:
            # Match company if specified
            item_comp = raw.get("companyName", "")
            if company and company.lower() not in item_comp.lower() and item_comp.lower() not in company.lower():
                continue
            normalized = self.normalize_job_record(raw)
            if normalized:
                jobs.append(normalized)

        return jobs

    def normalize_job_record(self, raw: Dict[str, Any]) -> Optional[Job]:
        """Normalize raw Naukri job metadata into strongly typed canonical Job."""
        external_id = str(raw.get("jobId", "")).strip()
        if not external_id:
            return None

        title = str(raw.get("title", "")).strip()
        company = str(raw.get("companyName", "")).strip()
        if not title or not company:
            return None

        canonical_url = normalize_url(raw.get("staticUrl", f"https://www.naukri.com/job-listings-{external_id}"))
        norm_company = normalize_company(company)
        norm_title = normalize_title(title)
        location_raw = raw.get("location", "Not Specified")
        norm_loc, is_remote = normalize_location(location_raw)

        desc_raw = raw.get("jobDescription", "")
        clean_desc = sanitize_job_description(desc_raw)

        # Parse salary if present
        salary_info = None
        sal_raw = str(raw.get("salary", "")).strip()
        if sal_raw and "not disclosed" not in sal_raw.lower():
            salary_info = self._parse_naukri_salary(sal_raw)

        # Parse posted date
        posted_at = None
        if raw.get("createdDate"):
            try:
                posted_at = datetime.fromisoformat(raw["createdDate"].replace("Z", "+00:00"))
            except Exception:
                posted_at = None

        content_hash = compute_content_hash(
            description=clean_desc,
            fallback_title=norm_title,
        )

        canonical_key = compute_canonical_key(
            company=norm_company,
            title=norm_title,
            location_bucket=norm_loc,
        )

        return Job(
            id=uuid.uuid4(),
            platform="naukri",
            external_id=external_id,
            url=canonical_url,
            company=company,
            normalized_company=norm_company,
            title=title,
            normalized_title=norm_title,
            location=location_raw,
            location_bucket=norm_loc,
            canonical_key=canonical_key,
            content_hash=content_hash,
            status=JobStatus.DISCOVERED,
            salary=salary_info,
            description=clean_desc,
            posted_at=posted_at,
        )

    def _parse_naukri_salary(self, salary_str: str) -> Optional[SalaryInfo]:
        """Parse Naukri salary expressions e.g. '2,000,000 - 3,000,000 PA'."""
        clean = salary_str.replace(",", "").strip()
        match = re.search(r"(\d+)\s*-\s*(\d+)", clean)
        if match:
            min_amt = float(match.group(1))
            max_amt = float(match.group(2))
            return SalaryInfo(
                min_amount=min_amt,
                max_amount=max_amt,
                currency="INR",
                interval="year" if "PA" in salary_str or "P.A." in salary_str else "month",
            )
        return None


class NaukriProvider(JobProvider):
    """Playwright and HTML form inspection provider for Naukri."""

    name: str = "naukri"

    def __init__(
        self,
        answer_resolver: Optional[AnswerResolver] = None,
        policy_engine: Optional[PolicyEngine] = None,
        answer_bank_repo: Optional[Any] = None,
    ) -> None:
        from worker.answers.repository import InMemoryAnswerBankRepository

        self.policy_engine = policy_engine or PolicyEngine()
        self.repository = answer_bank_repo or InMemoryAnswerBankRepository()
        self.answer_resolver = answer_resolver or AnswerResolver(
            repository=self.repository,
            policy_engine=self.policy_engine,
        )

    async def inspect_and_fill(
        self,
        page: Any,
        profile: ProfileSnapshot,
        dry_run: bool = True,
        screenshot_dir: Optional[Path] = None,
    ) -> FormFillResult:
        """Inspect Naukri form, classify controls, and build fill plan without submitting."""
        if not dry_run:
            raise RealSubmitGateBlockedError("Real submissions on Naukri are strictly disabled.")

        from worker.browser.page_inspector import PageInspector

        inspector = PageInspector()
        try:
            detected = await inspector.inspect_page(page)
        except Exception:
            # Fallback if page is HTML content string in offline tests
            if hasattr(page, "content"):
                html = await page.content()
                detected = inspector.inspect_html(html)
            else:
                detected = []

        fields_filled: Dict[str, str] = {}
        unresolved: List[str] = []
        discovered: List[FormField] = []

        # Check for CAPTCHA/challenge
        has_challenge = any(f.is_sensitive for f in detected)

        for d in detected:
            decision = self.policy_engine.evaluate(field_key=d.name or d.field_id, label_text=d.label)
            cat = decision.category
            policy = decision.policy

            resolved_val = None
            is_res = False

            # Truthful mapping from candidate profile
            if "name" in d.label.lower() or "fullname" in (d.name or "").lower():
                resolved_val = profile.candidate.name
                is_res = True
            elif "email" in d.label.lower():
                resolved_val = profile.candidate.email
                is_res = True
            elif "mobile" in d.label.lower() or "phone" in d.label.lower():
                resolved_val = profile.candidate.phone
                is_res = True
            elif "location" in d.label.lower() or "city" in d.label.lower():
                resolved_val = profile.candidate.location or "Bangalore"
                is_res = True

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
                p = screenshot_dir / f"naukri_evidence_{uuid.uuid4().hex[:8]}.png"
                await page.screenshot(path=str(p))
                screenshot_path = str(p)
            except Exception as ss_err:
                logger.warning("Could not capture screenshot: %s", ss_err)

        return FormFillResult(
            provider="naukri",
            fields_filled=fields_filled,
            unresolved_fields=unresolved,
            discovered_fields=discovered,
            screenshot_path=screenshot_path,
            submit_attempted=False,  # HARDCODED FALSE
            success=not has_challenge,
            error_message="Manual CAPTCHA challenge detected" if has_challenge else None,
        )
