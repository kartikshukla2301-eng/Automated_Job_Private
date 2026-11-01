"""Central JobApplicationRunner mediating all job board automation through SafetyEngine."""

import logging
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from worker.core.exceptions import SafetyBlockedError
from worker.core.safety import SafetyDecision, SafetyEngine
from worker.profile.models import ProfileSnapshot
from worker.profile.source import ProfileSource
from worker.providers.base import FormFillResult, JobProvider

logger = logging.getLogger("worker.core.runner")


def validate_and_resolve_fixture_uri(target: str, fixtures_dir: Path) -> str:
    """Validate and resolve a local fixture path or file:// URI, rejecting external URLs and path traversal.

    CRITICAL SAFETY RULES (Phase 0.6):
    - Only local fixture files within approved fixtures_dir are permitted.
    - External schemes (http, https, ftp, ws, wss, javascript, data) are strictly prohibited.
    - Path traversal attempts outside fixtures_dir are strictly rejected.
    """
    clean_target = target.strip()
    parsed = urllib.parse.urlparse(clean_target)

    # 1. Reject unexpected or external schemes
    if parsed.scheme.lower() in ("http", "https", "ftp", "ws", "wss", "javascript", "data"):
        raise ValueError(
            f"External navigation rejected: Scheme '{parsed.scheme}' is prohibited. "
            "Only verified local fixtures inside the approved directory are permitted."
        )

    # On Windows, absolute paths like C:\... are parsed with scheme="c"
    is_windows_drive = len(parsed.scheme) == 1 and parsed.scheme.isalpha()

    if parsed.scheme and parsed.scheme != "file" and not is_windows_drive:
        raise ValueError(
            f"Unsupported scheme '{parsed.scheme}'. Only local fixture paths or 'file://' URIs are permitted."
        )

    # 2. Extract filesystem path
    if parsed.scheme == "file":
        local_path_str = urllib.request.url2pathname(parsed.path)
        if len(local_path_str) > 2 and local_path_str[0] == "/" and local_path_str[2] == ":":
            local_path_str = local_path_str[1:]
        path = Path(local_path_str)
    else:
        path = Path(clean_target)

    # 3. Resolve path and verify existence
    try:
        resolved_path = path.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise ValueError(f"Fixture file does not exist: {clean_target}") from exc

    if not resolved_path.is_file():
        raise ValueError(f"Target fixture path must be a file, not a directory: {resolved_path}")

    # 4. Enforce containment inside approved fixtures directory (anti-path traversal)
    approved_dir = fixtures_dir.resolve()
    try:
        resolved_path.relative_to(approved_dir)
    except ValueError as exc:
        raise ValueError(
            f"Path traversal rejected: Fixture '{resolved_path}' is outside approved directory '{approved_dir}'"
        ) from exc

    return resolved_path.as_uri()


class DryRunExecutionResult(BaseModel):
    """Auditable evidence result of a completed dry-run form inspection and fill."""

    job_url: str = Field(..., description="Target job vacancy URL or local fixture path")
    company: str = Field(..., description="Target company name")
    provider: str = Field(..., description="Job board provider name")
    profile_version: str = Field(..., description="Candidate profile version hash used for filling")
    fields_filled: Dict[str, str] = Field(
        default_factory=dict,
        description="Fields truthfully resolved and filled into the form",
    )
    unresolved_fields: List[str] = Field(
        default_factory=list,
        description="Fields requiring user review or Answer Bank resolution",
    )
    screenshot_path: Optional[str] = Field(
        default=None,
        description="Path to captured full-page form evidence screenshot",
    )
    status: str = Field(default="DRY_RUN_COMPLETED", description="Execution lifecycle status")
    executed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the dry-run execution",
    )
    safety_decision: Optional[SafetyDecision] = Field(
        default=None,
        description="Safety barrier decision recorded before execution",
    )


class JobApplicationRunner:
    """Central orchestrator for all job application actions.

    MANDATORY ARCHITECTURE RULE (AD-006 & Architecture v1.0 LOCKED):
    All provider execution MUST be initiated through this runner.
    The runner unconditionally invokes SafetyEngine.verify_pre_apply()
    before any browser launch, navigation, or provider interaction.
    """

    def __init__(
        self,
        safety_engine: SafetyEngine,
        profile_source: ProfileSource,
        providers: Optional[Dict[str, JobProvider]] = None,
        evidence_dir: Optional[Path] = None,
        fixtures_dir: Optional[Path] = None,
    ) -> None:
        self.safety_engine = safety_engine
        self.profile_source = profile_source
        if providers is not None:
            self.providers = providers
        else:
            from worker.providers.greenhouse import GreenhouseProvider
            self.providers = {"greenhouse": GreenhouseProvider()}
        self.evidence_dir = evidence_dir or Path("worker/sessions/evidence")
        self.fixtures_dir = (fixtures_dir or Path("fixtures/forms")).resolve()

    async def execute_dry_run(
        self,
        job_url_or_path: str,
        company: str,
        provider_name: str,
        page: Optional[Any] = None,
    ) -> DryRunExecutionResult:
        """Execute a safe, auditable dry-run application on a target job form.

        Args:
            job_url_or_path: URL or local file path to the job posting.
            company: Target employer company name.
            provider_name: Provider identifier (e.g. 'greenhouse').
            page: Optional pre-configured Playwright Page instance (e.g. in test fixtures).

        Returns:
            DryRunExecutionResult: Auditable record of fields resolved, unfilled, and evidence.

        Raises:
            SafetyBlockedError: If kill switch is active, caps exceeded, or safety state invalid.
            ValueError: If target URL is external/disallowed or provider is unknown.
        """
        # 1. MANDATORY SAFETY BARRIER: Fail closed before touching browser or provider
        self.safety_engine.verify_pre_apply(
            company=company,
            provider=provider_name,
            is_real_submit=False,
        )

        # 2. VALIDATE TARGET FIXTURE NAVIGATION (Fail closed before any browser action)
        target_uri = validate_and_resolve_fixture_uri(job_url_or_path, self.fixtures_dir)

        norm_provider = provider_name.strip().lower()
        provider = self.providers.get(norm_provider)
        if not provider:
            raise ValueError(f"Unsupported job board provider: '{provider_name}'")

        # 3. Retrieve verified candidate profile snapshot
        profile: ProfileSnapshot = await self.profile_source.get_snapshot()

        # 4. Execute dry-run with browser page
        if page is not None:
            # Caller provided page (e.g. unit test fixture)
            fill_result: FormFillResult = await provider.inspect_and_fill(
                page=page,
                profile=profile,
                dry_run=True,
                screenshot_dir=self.evidence_dir,
            )
        else:
            # Self-managed Playwright session
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                ctx = await browser.new_context()
                browser_page = await ctx.new_page()
                try:
                    await browser_page.goto(target_uri)
                    fill_result = await provider.inspect_and_fill(
                        page=browser_page,
                        profile=profile,
                        dry_run=True,
                        screenshot_dir=self.evidence_dir,
                    )
                finally:
                    await browser.close()

        if not fill_result.success:
            logger.error("Provider dry-run reported failure: %s", fill_result.error_message)

        return DryRunExecutionResult(
            job_url=job_url_or_path,
            company=company,
            provider=norm_provider,
            profile_version=profile.profile_version,
            fields_filled=fill_result.fields_filled,
            unresolved_fields=fill_result.unresolved_fields,
            screenshot_path=fill_result.screenshot_path,
            status="DRY_RUN_COMPLETED" if fill_result.success else "DRY_RUN_FAILED",
            safety_decision=SafetyDecision(
                allowed=True,
                reason="Pre-apply safety checks passed; dry-run executed.",
            ),
        )
