"""End-to-end walking skeleton integration workflow."""

import logging
from pathlib import Path
from typing import Any, Optional

from worker.core.runner import DryRunExecutionResult, JobApplicationRunner
from worker.core.safety import SafetyEngine
from worker.profile.source import ProfileSource

logger = logging.getLogger("worker.core.workflow")

APPROVED_GREENHOUSE_FIXTURE_REL = Path("fixtures/forms/greenhouse_job.html")


class WalkingSkeletonWorkflow:
    """Coordinates the safe end-to-end walking skeleton dry run.

    ARCHITECTURAL CONSTRAINTS (Phase 0.8):
    - Bound strictly to the approved local Greenhouse HTML fixture.
    - Never accepts or navigates to arbitrary external URLs or arbitrary paths.
    - Enforces pre-application safety barrier check before any browser launch.
    - Leaves ambiguous questions and sensitive input fields unfilled.
    - Never clicks submit.
    - Produces a typed, auditable dry-run result.
    """

    def __init__(
        self,
        runner: Optional[JobApplicationRunner] = None,
        safety_engine: Optional[SafetyEngine] = None,
        profile_source: Optional[ProfileSource] = None,
        fixture_path: Optional[Path] = None,
        evidence_dir: Optional[Path] = None,
    ) -> None:
        self.fixture_path = (fixture_path or APPROVED_GREENHOUSE_FIXTURE_REL).resolve()
        self.evidence_dir = (evidence_dir or Path("worker/sessions/evidence")).resolve()

        if runner is not None:
            self.runner = runner
        else:
            if safety_engine is None or profile_source is None:
                raise ValueError(
                    "Must provide either a pre-configured runner or both safety_engine and profile_source."
                )
            from worker.providers.greenhouse import GreenhouseProvider

            self.runner = JobApplicationRunner(
                safety_engine=safety_engine,
                profile_source=profile_source,
                providers={"greenhouse": GreenhouseProvider()},
                evidence_dir=self.evidence_dir,
                fixtures_dir=self.fixture_path.parent,
            )

    async def run_greenhouse_dry_run(
        self,
        company: str = "Example Software",
        page: Optional[Any] = None,
    ) -> DryRunExecutionResult:
        """Execute a safe, auditable dry run against the approved Greenhouse fixture.

        Args:
            company: Target employer company name.
            page: Optional Playwright page instance (e.g. for testing).

        Returns:
            DryRunExecutionResult: Auditable record of fields resolved, unfilled, and evidence.
        """
        if not self.fixture_path.exists():
            raise FileNotFoundError(f"Approved Greenhouse fixture missing at '{self.fixture_path}'")

        logger.info(
            "Initiating walking skeleton Greenhouse dry-run for '%s' on approved fixture '%s'",
            company,
            self.fixture_path,
        )

        return await self.runner.execute_dry_run(
            job_url_or_path=str(self.fixture_path),
            company=company,
            provider_name="greenhouse",
            page=page,
        )
