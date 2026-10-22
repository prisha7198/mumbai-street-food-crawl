"""Diversity re-ranking with Maximal Marginal Relevance.

Carbonell & Goldstein (1998). Build the list one item at a time, each time
picking the candidate that maximises

    lambda * relevance(i) - (1 - lambda) * max_{j already picked} sim(i, j)

With lambda = 0.7 relevance still leads, but a third vada pav stall right
after two others pays a price for being similar to them.

Intra-list similarity (Ziegler et al., 2005) is the mean pairwise
similarity of a list: lower means more varied.
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .. import config


def mmr(relevance: np.ndarray, sim: np.ndarray, n: int, lam: float = config.MMR_LAMBDA) -> list[int]:
    """Return indices in MMR order (length min(n, len(relevance)))."""
    remaining = list(range(len(relevance)))
    picked: list[int] = []
    while remaining and len(picked) < n:
        if not picked:
            best = max(remaining, key=lambda i: relevance[i])
        else:
            best = max(remaining, key=lambda i: lam * relevance[i] - (1 - lam) * sim[i, picked].max())
        picked.append(best)
        remaining.remove(best)
    return picked


def intra_list_similarity(vectors: np.ndarray) -> float:
    n = vectors.shape[0]
    if n < 2:
        return 0.0
    s = cosine_similarity(vectors)
    return float(s[np.triu_indices(n, k=1)].mean())


def similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    return cosine_similarity(vectors) if vectors.shape[0] else np.zeros((0, 0))
