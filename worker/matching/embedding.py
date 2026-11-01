"""Local Embedding Provider abstraction and deterministic fallback.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 10)
- docs/BUILD_RULES.md

CRITICAL INVARIANTS:
1. No direct external embedding API calls.
2. Local sentence-transformer model (e.g. all-MiniLM-L6-v2, 384-d) when installed.
3. If local neural model is unavailable, provide a deterministic offline fallback
   and document the limitation explicitly. Do NOT claim lexical similarity is
   neural embedding similarity.
4. Pure standard-library vector math (cosine similarity, normalization).
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Any, List, Optional, Protocol, runtime_checkable

logger = logging.getLogger("worker.matching.embedding")


class EmbeddingError(Exception):
    """Base exception for embedding operations."""


class EmbeddingModelUnavailableError(EmbeddingError):
    """Raised when the specified local embedding model is not installed or available."""


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors in pure Python.

    Returns float in range [-1.0, 1.0], normalized to [0.0, 1.0] for non-negative vectors.
    Returns 0.0 if either vector has zero magnitude or if dimensions mismatch.
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    sim = dot_product / (norm_a * norm_b)
    # Clamp float precision boundaries
    return max(0.0, min(1.0, (sim + 1.0) / 2.0 if sim < 0.0 else sim))


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol defining the embedding interface."""

    dimension: int

    async def embed_text(self, text: str) -> List[float]:
        """Generate vector embedding for a single text string."""
        ...

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate vector embeddings for a batch of text strings."""
        ...

    def similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Compute similarity score (0.0 to 1.0) between two vectors."""
        ...


class LocalSentenceTransformerEmbeddingProvider:
    """Production provider using local SentenceTransformers model.

    Target model: all-MiniLM-L6-v2 (384 dimensions).
    Runs 100% locally on CPU or local GPU with zero external network calls.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self.dimension = 384
        self._model = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(self.model_name)
            return self._model
        except ImportError as err:
            raise EmbeddingModelUnavailableError(
                f"sentence-transformers package is not installed. "
                f"Install with `pip install sentence-transformers` or use DeterministicFallbackEmbeddingProvider. "
                f"Original error: {err}"
            ) from err
        except Exception as err:
            raise EmbeddingModelUnavailableError(
                f"Failed to load local embedding model '{self.model_name}': {err}"
            ) from err

    async def embed_text(self, text: str) -> List[float]:
        model = self._load_model()
        vec = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return [float(x) for x in vec.tolist()]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        model = self._load_model()
        vecs = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return [[float(x) for x in v.tolist()] for v in vecs]

    def similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        return cosine_similarity(vec_a, vec_b)


class DeterministicFallbackEmbeddingProvider:
    """Offline, deterministic hashed n-gram embedding fallback.

    Produces stable 384-dimensional unit vectors using Murmur3/SHA256 feature hashing.
    Used for offline testing and environments where SentenceTransformers / PyTorch
    are not installed.

    NOTE: This is a deterministic feature-hashing fallback, NOT a neural language model.
    """

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _vectorize(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self.dimension

        vec = [0.0] * self.dimension
        tokens = re.findall(r"\b[a-zA-Z0-9_\+#\.\-]{2,}\b", text.lower())

        if not tokens:
            return [0.0] * self.dimension

        # Feature hashing of unigrams and bigrams
        features = list(tokens)
        for i in range(len(tokens) - 1):
            features.append(f"{tokens[i]}_{tokens[i+1]}")

        for feat in features:
            h = int(hashlib.md5(feat.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if ((h >> 16) & 1) == 0 else -1.0
            vec[idx] += sign

        # Unit normalization
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [v / norm for v in vec]
        return vec

    async def embed_text(self, text: str) -> List[float]:
        return self._vectorize(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._vectorize(t) for t in texts]

    def similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        return cosine_similarity(vec_a, vec_b)
