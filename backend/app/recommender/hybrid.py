"""Blend the three scores into one.

Each component is min-max normalised to 0..1 over the candidates that
survived the filters, so no component dominates just because of its scale.
Then:

    score = w_content * content + w_quality * quality + w_cf * cf
            - wait_penalty - hygiene_penalty

Without a profile there is no CF, and its weight is shared out between
content and quality in proportion to their own weights (0.45 : 0.30 -> 0.6 : 0.4).
"""
from __future__ import annotations

import numpy as np

from .. import config
from ..models import Stall


def minmax(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    lo, hi = float(x.min()), float(x.max())
    if hi - lo < 1e-9:
        return np.ones_like(x, dtype=float)   # all equal: nobody is worse than anybody else
    return (x - lo) / (hi - lo)


def effective_weights(use_cf: bool) -> dict[str, float]:
    w = dict(config.HYBRID_WEIGHTS)
    if not use_cf:
        rest = w["content"] + w["quality"]
        w = {"content": w["content"] / rest, "quality": w["quality"] / rest, "cf": 0.0}
    return w


def penalties(stalls: list[Stall]) -> np.ndarray:
    out = np.zeros(len(stalls))
    for i, s in enumerate(stalls):
        span = config.WAIT_PENALTY_FULL - config.WAIT_PENALTY_FROM
        wait = np.clip((s.avg_wait_minutes - config.WAIT_PENALTY_FROM) / span, 0, 1) * config.WAIT_PENALTY
        hyg = max(0, config.HYGIENE_OK - s.hygiene_score) / (config.HYGIENE_OK - 1) * config.HYGIENE_PENALTY
        out[i] = wait + hyg
    return out


def blend(content: np.ndarray, quality: np.ndarray, cf: np.ndarray | None, stalls: list[Stall]) -> dict:
    use_cf = cf is not None
    w = effective_weights(use_cf)
    c, q = minmax(content), minmax(quality)
    f = minmax(cf) if use_cf else np.zeros_like(c)
    pen = penalties(stalls)
    score = w["content"] * c + w["quality"] * q + w["cf"] * f - pen
    return {
        "weights": w,
        "content": c, "quality": q, "cf": f, "penalty": pen,
        # the weighted parts, used for the stacked bar in the UI
        "parts": {"content": w["content"] * c, "quality": w["quality"] * q, "cf": w["cf"] * f},
        "score": score,
    }
