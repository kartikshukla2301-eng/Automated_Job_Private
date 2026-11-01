"""Deduplication safety analysis and cross-platform identity classification.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10, Dedupe and Cooldown RC-9)
- docs/BUILD_RULES.md

CRITICAL INVARIANTS:
1. Key 1: (platform, external_id) - exact provider-level identity.
2. Key 2: canonical_key = normalized_company + ":" + normalized_title + ":" + location_bucket.
3. Key 3: content_hash match OR embedding similarity >= 0.95 for cross-platform duplicate identity.
4. Do NOT automatically merge two distinct job requisitions merely because company,
   title and location match. Distinct requisitions for different teams must not be lost!
5. Preserve provider-specific external IDs.
"""

from __future__ import annotations

from enum import Enum
import logging
from typing import Optional

from worker.discovery.models import Job
from worker.matching.embedding import EmbeddingProvider

logger = logging.getLogger("worker.matching.deduplication")


class DuplicateClassification(str, Enum):
    """Classification of relationship between two job listings."""

    IDENTICAL_EXTERNAL_ID = "IDENTICAL_EXTERNAL_ID"  # Key 1: Same platform and external ID
    CROSS_PLATFORM_EXACT = "CROSS_PLATFORM_EXACT"  # Key 2 + Key 3: Same canonical key + content_hash or sim >= 0.95
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"  # Key 2 match, but different descriptions/content_hash (distinct teams?)
    DISTINCT_OPENING = "DISTINCT_OPENING"  # Different canonical keys entirely


async def classify_duplicate_relationship(
    job_a: Job,
    job_b: Job,
    embedding_provider: Optional[EmbeddingProvider] = None,
) -> DuplicateClassification:
    """Classify deduplication relationship between two job records.

    Ensures distinct job openings are preserved while identifying cross-platform duplicates.
    """
    # Key 1: Exact provider identity
    if job_a.platform.lower() == job_b.platform.lower() and job_a.external_id == job_b.external_id:
        return DuplicateClassification.IDENTICAL_EXTERNAL_ID

    # If canonical keys differ, they are distinct openings
    if job_a.canonical_key != job_b.canonical_key:
        return DuplicateClassification.DISTINCT_OPENING

    # Canonical keys match (same normalized company, title, and location bucket)
    # Now check Key 3: Content hash or embedding similarity >= 0.95
    if job_a.content_hash == job_b.content_hash:
        return DuplicateClassification.CROSS_PLATFORM_EXACT

    # Check embedding similarity if embeddings are present or provider is available
    if job_a.embedding and job_b.embedding and embedding_provider:
        sim = embedding_provider.similarity(job_a.embedding, job_b.embedding)
        if sim >= 0.95:
            return DuplicateClassification.CROSS_PLATFORM_EXACT

    # If descriptions differ and embedding similarity is below 0.95 (or unavailable),
    # classify as POSSIBLE_DUPLICATE. Do not merge or discard; preserve as distinct opening!
    return DuplicateClassification.POSSIBLE_DUPLICATE
