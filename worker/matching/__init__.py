"""Matching and scoring engine package exports.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10)
"""

from worker.matching.borderline import review_borderline_job
from worker.matching.deduplication import (
    DuplicateClassification,
    classify_duplicate_relationship,
)
from worker.matching.embedding import (
    DeterministicFallbackEmbeddingProvider,
    EmbeddingError,
    EmbeddingModelUnavailableError,
    EmbeddingProvider,
    LocalSentenceTransformerEmbeddingProvider,
    cosine_similarity,
)
from worker.matching.hard_filters import (
    evaluate_hard_filters,
    extract_min_experience_years,
)
from worker.matching.models import (
    DEFAULT_SCORING_WEIGHTS,
    CandidateJobPreferences,
    HardFilterResult,
    JobMatchRequest,
    JobMatchResult,
    MatchDecision,
    MatchExplanation,
    MatchScoreBreakdown,
)
from worker.matching.scoring import calculate_match_score
from worker.matching.service import JobMatchingService

__all__ = [
    "CandidateJobPreferences",
    "DEFAULT_SCORING_WEIGHTS",
    "DeterministicFallbackEmbeddingProvider",
    "DuplicateClassification",
    "EmbeddingError",
    "EmbeddingModelUnavailableError",
    "EmbeddingProvider",
    "HardFilterResult",
    "JobMatchRequest",
    "JobMatchResult",
    "JobMatchingService",
    "LocalSentenceTransformerEmbeddingProvider",
    "MatchDecision",
    "MatchExplanation",
    "MatchScoreBreakdown",
    "calculate_match_score",
    "classify_duplicate_relationship",
    "cosine_similarity",
    "evaluate_hard_filters",
    "extract_min_experience_years",
    "review_borderline_job",
]
