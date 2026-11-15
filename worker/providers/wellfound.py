"""Wellfound (formerly AngelList) job provider adapter, discovery, and session management foundation (Phase 1.7).

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

logger = logging.getLogger("worker.providers.wellfound")


class WellfoundSessionStatus(str, Enum):
    LOGGED_IN = "LOGGED_IN"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"


class WellfoundSessionManager:
    """Manages persistent manual user session tokens and cookies for Wellfound."""

    def __init__(self, session_path: Path = Path("worker/sessions/wellfound/cookies.json")) -> None:
        self.session_path = session_path

    def load_session(self) -> Dict[str, Any]:
        """Load saved session metadata if it exists."""
        if not self.session_path.exists():
            return {}
        try:
            return json.loads(self.session_path.read_text(encoding="utf-8"))
        except Exception as err:
            logger.warning("Could not read Wellfound session file: %s", err)
            return {}

    def save_session(self, cookies: List[Dict[str, Any]], user_identifier: str = "") -> None:
        """Persist session cookies. Never store user credentials or passwords."""
        for cookie in cookies:
            cookie_str = json.dumps(cookie).lower()
            if "password" in cookie_str or "secret" in cookie_str:
                raise ValueError("Security violation: attempt to store credentials in session storage")

        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "user_identifier": user_identifier,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "cookies": cookies,
        }
        self.session_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Saved Wellfound session for %s", user_identifier or "unspecified user")

    def check_session_status(self) -> WellfoundSessionStatus:
        """Check if session file is present and not expired."""
        data = self.load_session()
        if not data or "cookies" not in data or not data["cookies"]:
            return WellfoundSessionStatus.LOGIN_REQUIRED

        saved_at_str = data.get("saved_at")
        if not saved_at_str:
            return WellfoundSessionStatus.LOGIN_REQUIRED

        try:
            saved_at = datetime.fromisoformat(saved_at_str)
            age_hours = (datetime.now(timezone.utc) - saved_at).total_seconds() / 3600.0
            if age_hours > 720.0:  # 30 days
                return WellfoundSessionStatus.SESSION_EXPIRED
        except Exception:
            return WellfoundSessionStatus.LOGIN_REQUIRED

        return WellfoundSessionStatus.LOGGED_IN


class WellfoundDiscoveryAdapter(JobDiscoveryAdapter):
    """Parses raw Wellfound startup job listings into canonical Job models."""

    def __init__(self) -> None:
        pass

    def parse_job_payload(self, raw_data: Dict[str, Any]) -> Optional[Job]:
        """Convert a Wellfound job dictionary into a strongly typed Job model."""
        external_id = str(raw_data.get("id") or "")
        title = raw_data.get("title") or ""
        company = raw_data.get("company_name") or raw_data.get("company", {}).get("name") if isinstance(raw_data.get("company"), dict) else raw_data.get("company_name") or ""
        url = raw_data.get("url") or raw_data.get("absolute_url") or ""

        if not external_id or not title or not company or not url:
            logger.warning("Skipping malformed Wellfound job record: missing core fields")
            return None

        if not is_safe_discovery_url(url):
            logger.warning("Unsafe discovery URL rejected: %s", url)
            return None

        canonical_url = normalize_url(url)
        norm_company = normalize_company(company)
        norm_title = normalize_title(title)

        location_raw = raw_data.get("location") or "Remote"
        is_remote = bool(raw_data.get("remote", False))
        loc_input = f"{location_raw} (Remote)" if is_remote and "remote" not in location_raw.lower() else location_raw
        norm_location, loc_bucket = normalize_location(loc_input)
        canonical_key = compute_canonical_key(norm_company, norm_title, loc_bucket)

        raw_desc = raw_data.get("description") or ""
        clean_desc = sanitize_job_description(raw_desc)
        content_hash = compute_content_hash(clean_desc, fallback_title=title)

        salary_info: Optional[SalaryInfo] = None
        comp_str = raw_data.get("compensation") or ""
        if comp_str:
            salary_info = self._parse_compensation(comp_str)

        # Detect already applied status
        already_applied = bool(raw_data.get("already_applied", False))
        status = JobStatus.APPLIED if already_applied else JobStatus.DISCOVERED

        return Job(
            id=uuid.uuid4(),
            platform="wellfound",
            external_id=external_id,
            url=canonical_url,
            canonical_key=canonical_key,
            company=company,
            normalized_company=norm_company,
            title=title,
            normalized_title=norm_title,
            location=norm_location,
            location_bucket=loc_bucket,
            employment_type=raw_data.get("job_type", "Full-Time"),
            experience_requirements=raw_data.get("experience_years"),
            salary=salary_info,
            description=clean_desc,
            content_hash=content_hash,
            status=status,
            metadata={
                "wellfound_slug": raw_data.get("slug"),
                "already_applied": already_applied,
                "remote": is_remote,
            },
        )

    def parse_job_list(self, raw_list: List[Dict[str, Any]]) -> List[Job]:
        """Parse multiple Wellfound job entries."""
        jobs: List[Job] = []
        for item in raw_list:
            parsed = self.parse_job_payload(item)
            if parsed:
                jobs.append(parsed)
        return jobs

    def _parse_compensation(self, comp_str: str) -> Optional[SalaryInfo]:
        """Extract numeric salary ranges from Wellfound compensation strings like '$140k – $180k'."""
        try:
            currency = "$" if "$" in comp_str else "USD"
            nums = re.findall(r"\$?(\d+(?:\.\d+)?)\s*k", comp_str, re.IGNORECASE)
            if len(nums) >= 2:
                min_val = float(nums[0]) * 1000.0
                max_val = float(nums[1]) * 1000.0
                return SalaryInfo(
                    currency=currency,
                    min_amount=min_val,
                    max_amount=max_val,
                    interval="year",
                )
            elif len(nums) == 1:
                amt = float(nums[0]) * 1000.0
                return SalaryInfo(
                    currency=currency,
                    min_amount=amt,
                    max_amount=amt,
                    interval="year",
                )
            return None
        except Exception:
            return None


class WellfoundProvider(JobProvider):
    """Playwright-based provider for inspecting Wellfound job applications.
    
    Adheres strictly to L0 dry-run safety and never mutates forms or clicks submit.
    """

    name: str = "wellfound"

    def __init__(
        self,
        policy_engine: Optional[PolicyEngine] = None,
        answer_resolver: Optional[AnswerResolver] = None,
        session_manager: Optional[WellfoundSessionManager] = None,
    ) -> None:
        from worker.answers.repository import InMemoryAnswerBankRepository

        self.policy_engine = policy_engine or PolicyEngine()
        self.repository = InMemoryAnswerBankRepository()
        self.answer_resolver = answer_resolver or AnswerResolver(
            repository=self.repository,
            policy_engine=self.policy_engine,
        )
        self.session_manager = session_manager or WellfoundSessionManager()

    async def inspect_form(self, page: Any) -> List[FormField]:
        """Inspect Wellfound application form and extract form fields."""
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
                scope="provider:wellfound",
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
                p = screenshot_dir / f"wellfound_evidence_{uuid.uuid4().hex[:8]}.png"
                await page.screenshot(path=str(p))
                screenshot_path = str(p)
            except Exception as ss_err:
                logger.warning("Could not capture screenshot: %s", ss_err)

        return FormFillResult(
            provider="wellfound",
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
