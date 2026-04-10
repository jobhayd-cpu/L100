from __future__ import annotations

import hashlib
import logging
import math
from typing import List, Optional

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _hash_embed(text: str, dim: int = 128) -> List[float]:
    """
    Deterministic fallback embedding based on character n-gram hashing.
    NOT suitable for semantic search but allows the system to function
    without an API key.
    """
    vec = [0.0] * dim
    text = text.lower()
    for i in range(len(text) - 2):
        ngram = text[i : i + 3]
        h = int(hashlib.sha256(ngram.encode()).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0

    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _pad_or_truncate(vec: List[float], dim: int) -> List[float]:
    if len(vec) == dim:
        return vec
    if len(vec) > dim:
        return vec[:dim]
    return vec + [0.0] * (dim - len(vec))


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed a list of texts.
    - If OPENAI_API_KEY is set, uses the OpenAI embedding model.
    - Otherwise, falls back to local hash-based embeddings (dim=128).
    Returns list of embedding vectors.
    """
    if not texts:
        return []

    if settings.has_openai:
        return _openai_embed(texts)

    dim = settings.embedding_dim
    logger.info("No OpenAI key — using local hash embeddings (dim=%d)", dim)
    return [_pad_or_truncate(_hash_embed(t, 128), dim) for t in texts]


def _openai_embed(texts: List[str]) -> List[List[float]]:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        # OpenAI recommends batches up to 2048 texts
        batch_size = 100
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = client.embeddings.create(model=settings.embedding_model, input=batch)
            all_embeddings.extend([item.embedding for item in response.data])
        return all_embeddings
    except Exception as exc:
        logger.error("OpenAI embedding failed: %s — falling back to local", exc)
        dim = settings.embedding_dim
        return [_pad_or_truncate(_hash_embed(t, 128), dim) for t in texts]


def embed_query(query: str) -> List[float]:
    """Embed a single query string."""
    return embed_texts([query])[0]
