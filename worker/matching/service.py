"""Central Job Matching and Scoring Service.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10)
- docs/BUILD_RULES.md
- config/config.yaml

PIPELINE:
Candidate ProfileSnapshot
    -> Candidate preferences
    -> Discovered jobs
    -> Hard eligibility filters
    -> Deterministic scoring
    -> Optional local embedding comparison
    -> Optional LLM borderline review
    -> Ranked MatchResults
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Tuple

from worker.core.llm_gateway import LLMGateway
from worker.discovery.models import Job, JobStatus
from worker.discovery.repository import JobRepository
from worker.matching.borderline import review_borderline_job
from worker.matching.embedding import EmbeddingProvider
from worker.matching.hard_filters import evaluate_hard_filters
from worker.matching.models import (
    DEFAULT_SCORING_WEIGHTS,
    CandidateJobPreferences,
    JobMatchRequest,
    JobMatchResult,
    MatchDecision,
    MatchExplanation,
    MatchScoreBreakdown,
)
from worker.profile.models import ProfileSnapshot

logger = logging.getLogger("worker.matching.service")

DECISION_SORT_ORDER: Dict[MatchDecision, int] = {
    MatchDecision.MATCH: 0,
    MatchDecision.BORDERLINE: 1,
    MatchDecision.UNRESOLVED: 2,
    MatchDecision.REJECT: 3,
    MatchDecision.EXCLUDED: 4,
}


class JobMatchingService:
    """Core domain service orchestrating candidate-job matching and scoring."""

    def __init__(
        self,
        repository: Optional[JobRepository] = None,
        llm_gateway: Optional[LLMGateway] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        threshold: float = 65.0,
        borderline_band: Tuple[float, float] = (55.0, 70.0),
        scoring_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.repository = repository
        self.llm_gateway = llm_gateway
        self.embedding_provider = embedding_provider
        self.threshold = threshold
        self.borderline_band = borderline_band
        self.scoring_weights = scoring_weights or dict(DEFAULT_SCORING_WEIGHTS)

    async def match_job(self, request: JobMatchRequest) -> JobMatchResult:
        """Evaluate a single candidate-job match request through the complete pipeline."""
        job = request.job
        profile = request.profile
        preferences = request.preferences or CandidateJobPreferences.from_profile(profile)
        now = datetime.now(timezone.utc)

        # 1. Evaluate Hard Eligibility Filters (Cannot be overridden by score or LLM)
        hard_filter_res = evaluate_hard_filters(
            job=job,
            preferences=preferences,
            applied_company_cooldowns=request.applied_company_cooldowns,
            applied_company_counts_today=request.applied_company_counts_today,
            applied_job_ids=request.applied_job_ids,
            now=now,
        )

        if not hard_filter_res.passed:
            breakdown = MatchScoreBreakdown(
                required_skills_score=0.0,
                role_relevance_score=0.0,
                experience_fit_score=0.0,
                preferred_skills_score=0.0,
                location_work_mode_score=0.0,
                project_evidence_score=0.0,
                weights=self.scoring_weights,
                raw_score=0.0,
                final_score=0.0,
            )
            explanation = MatchExplanation(
                positive_contributions=[],
                negative_contributions=hard_filter_res.reasons,
                missing_information=hard_filter_res.missing_fields,
                summary=f"Excluded by hard filter: {'; '.join(hard_filter_res.reasons)}",
            )
            result = JobMatchResult(
                job_id=job.id,
                platform=job.platform,
                external_id=job.external_id,
                canonical_key=job.canonical_key,
                company=job.company,
                title=job.title,
                decision=MatchDecision.EXCLUDED,
                passed_hard_filters=False,
                hard_filter_reasons=hard_filter_res.reasons,
                score=0.0,
                breakdown=breakdown,
                explanation=explanation,
                evaluated_at=now,
            )

            if self.repository:
                await self.repository.update_score(
                    job_id=job.id,
                    score=0.0,
                    score_breakdown=breakdown.model_dump(),
                    status=JobStatus.REJECTED,
                )
            return result

        # 2. Deterministic Match Scoring
        from worker.matching.scoring import calculate_match_score

        breakdown, explanation = calculate_match_score(
            job=job,
            snapshot=profile,
            preferences=preferences,
            weights=self.scoring_weights,
        )

        # 3. Optional Local Embedding Comparison
        if self.embedding_provider:
            try:
                candidate_text = (
                    f"Candidate roles: {', '.join(preferences.roles)}. "
                    f"Skills: {', '.join(s.name for s in profile.candidate.skills)}. "
                    f"Experience: {', '.join(e.title for e in profile.candidate.experience)}."
                )
                job_text = f"{job.title} at {job.company}. {job.description or ''}"[:1500]

                cand_vec = await self.embedding_provider.embed_text(candidate_text)
                job_vec = await self.embedding_provider.embed_text(job_text)
                sim = self.embedding_provider.similarity(cand_vec, job_vec)
                breakdown = breakdown.model_copy(update={"embedding_similarity": round(sim, 4)})
            except Exception as err:
                logger.warning("Local embedding comparison failed for job %s: %s", job.id, err)

        # 4. Optional Borderline Review via LLMGateway
        decision: MatchDecision
        if request.allow_borderline_llm and (
            self.borderline_band[0] <= breakdown.raw_score <= self.borderline_band[1]
        ):
            decision, breakdown, explanation = await review_borderline_job(
                job=job,
                snapshot=profile,
                preferences=preferences,
                breakdown=breakdown,
                explanation=explanation,
                llm_gateway=self.llm_gateway,
                borderline_band=self.borderline_band,
                threshold=self.threshold,
            )
        else:
            decision = (
                MatchDecision.MATCH
                if breakdown.final_score >= self.threshold
                else MatchDecision.REJECT
            )

        result = JobMatchResult(
            job_id=job.id,
            platform=job.platform,
            external_id=job.external_id,
            canonical_key=job.canonical_key,
            company=job.company,
            title=job.title,
            decision=decision,
            passed_hard_filters=True,
            hard_filter_reasons=[],
            score=breakdown.final_score,
            breakdown=breakdown,
            explanation=explanation,
            evaluated_at=now,
        )

        # 5. Future-Compatible Repository Update
        if self.repository:
            new_status = (
                JobStatus.MATCHED
                if decision == MatchDecision.MATCH
                else JobStatus.REJECTED
            )
            await self.repository.update_score(
                job_id=job.id,
                score=result.score,
                score_breakdown=breakdown.model_dump(),
                status=new_status,
            )

        return result

    async def match_jobs_batch(
        self,
        requests: List[JobMatchRequest],
    ) -> List[JobMatchResult]:
        """Evaluate a batch of job match requests with stable, deterministic ranking."""
        results: List[JobMatchResult] = []
        for req in requests:
            res = await self.match_job(req)
            results.append(res)

        # Stable deterministic sort:
        # 1. Decision priority (MATCH > BORDERLINE > UNRESOLVED > REJECT > EXCLUDED)
        # 2. Score descending
        # 3. External ID ascending (deterministic tie-breaker)
        results.sort(
            key=lambda r: (
                DECISION_SORT_ORDER.get(r.decision, 99),
                -r.score,
                r.external_id,
            )
        )
        return results
