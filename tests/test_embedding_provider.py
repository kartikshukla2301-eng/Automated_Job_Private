"""Unit tests for local embedding provider abstraction, cosine similarity, and fallback.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10)
- docs/BUILD_RULES.md
"""

import math
import pytest

from worker.matching.embedding import (
    DeterministicFallbackEmbeddingProvider,
    EmbeddingModelUnavailableError,
    EmbeddingProvider,
    LocalSentenceTransformerEmbeddingProvider,
    cosine_similarity,
)


def test_cosine_similarity_identical_and_orthogonal():
    # Identical vectors
    v1 = [1.0, 0.0, 0.0]
    assert cosine_similarity(v1, v1) == 1.0

    # Orthogonal vectors
    v2 = [0.0, 1.0, 0.0]
    assert cosine_similarity(v1, v2) == 0.0

    # Parallel scaled vectors
    v3 = [2.0, 0.0, 0.0]
    assert cosine_similarity(v1, v3) == 1.0


def test_cosine_similarity_edge_cases():
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0


@pytest.mark.asyncio
async def test_deterministic_fallback_provider_properties():
    provider = DeterministicFallbackEmbeddingProvider(dimension=384)
    assert isinstance(provider, EmbeddingProvider)
    assert provider.dimension == 384

    text = "Senior Python Backend Engineer building distributed services with FastAPI and PostgreSQL"
    vec = await provider.embed_text(text)

    assert len(vec) == 384
    # Check unit normalization
    norm = math.sqrt(sum(x * x for x in vec))
    assert pytest.approx(norm, abs=1e-5) == 1.0

    # Test determinism
    vec2 = await provider.embed_text(text)
    assert vec == vec2


@pytest.mark.asyncio
async def test_deterministic_fallback_similarity_ranking():
    provider = DeterministicFallbackEmbeddingProvider(dimension=384)

    query = "Python developer with FastAPI experience"
    similar = "Senior Python engineer building REST APIs with FastAPI"
    different = "Pediatric nurse practitioner at metropolitan healthcare facility"

    vec_q = await provider.embed_text(query)
    vec_sim = await provider.embed_text(similar)
    vec_diff = await provider.embed_text(different)

    sim_score = provider.similarity(vec_q, vec_sim)
    diff_score = provider.similarity(vec_q, vec_diff)

    assert sim_score > diff_score
    assert sim_score > 0.3


@pytest.mark.asyncio
async def test_deterministic_fallback_batch_embedding():
    provider = DeterministicFallbackEmbeddingProvider(dimension=384)
    texts = ["Job 1", "Job 2", "Job 3"]
    vecs = await provider.embed_batch(texts)
    assert len(vecs) == 3
    assert all(len(v) == 384 for v in vecs)


def test_local_sentence_transformer_error_when_uninstalled():
    provider = LocalSentenceTransformerEmbeddingProvider(model_name="all-MiniLM-L6-v2")
    # In test environment without sentence_transformers, it raises EmbeddingModelUnavailableError
    with pytest.raises(EmbeddingModelUnavailableError, match="sentence-transformers package is not installed"):
        provider._load_model()
