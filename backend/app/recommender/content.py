"""Content-based score: cosine similarity between the intent vector and each stall."""
from __future__ import annotations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity


def content_scores(intent_vec: np.ndarray, stall_matrix: np.ndarray) -> np.ndarray:
    if stall_matrix.shape[0] == 0:
        return np.zeros(0)
    if not intent_vec.any():
        return np.zeros(stall_matrix.shape[0])
    return cosine_similarity(intent_vec.reshape(1, -1), stall_matrix)[0]
