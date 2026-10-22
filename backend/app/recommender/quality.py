"""Quality score: Bayesian average rating.

This is the IMDb weighted rating approach (used for its Top 250 list):

    WR = (v / (v + m)) * R + (m / (v + m)) * C

    R = the stall's own average rating
    v = how many reviews that rating is based on
    C = the mean rating across all stalls
    m = how many reviews we want before trusting R (60th percentile here)

A stall rated 4.9 from 6 reviews gets pulled towards the city average,
while a 4.6 from 2,000 reviews barely moves.
"""
from __future__ import annotations

import numpy as np

from .. import config
from ..models import Stall


def bayesian_params(stalls: list[Stall], percentile: float = config.BAYES_PERCENTILE) -> tuple[float, float]:
    """(C, m) computed over the whole catalogue."""
    ratings = np.array([s.rating for s in stalls], dtype=float)
    counts = np.array([s.review_count for s in stalls], dtype=float)
    return float(ratings.mean()), float(np.percentile(counts, percentile))


def bayesian_average(R: float, v: float, C: float, m: float) -> float:
    if v + m == 0:
        return C
    return (v / (v + m)) * R + (m / (v + m)) * C


def quality_scores(stalls: list[Stall], C: float, m: float) -> np.ndarray:
    return np.array([bayesian_average(s.rating, s.review_count, C, m) for s in stalls])
