"""Feature vectors for stalls and for the user's intent.

Every stall becomes one row vector made of five blocks:

    [ category one-hot | vibe multi-hot | spice (soft) | price (soft) | diet flags ]

The intent vector has exactly the same layout, so cosine similarity
between the two says how well a stall matches what was asked for.

Spice and price are numbers, and a raw number does not behave well inside a
cosine (bigger always looks "more similar"). So each is encoded as a soft
one-hot: a small Gaussian bump over the bins, centred on the normalised value.
Spice 4 then overlaps strongly with 5, a little with 3, and not at all with 1.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import config
from ..models import Preferences, Stall, User

SPICE_LEVELS = np.arange(1, 6)
N_PRICE_BINS = len(config.PRICE_BINS) - 1


def soft_bins(value: float, centres: np.ndarray, sigma: float) -> np.ndarray:
    v = np.exp(-((centres - value) ** 2) / (2 * sigma ** 2))
    return v / np.linalg.norm(v)


def price_position(price: float) -> float:
    """Continuous bin index for a price, e.g. ₹75 sits halfway through bin 1."""
    edges = config.PRICE_BINS
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        if price < hi:
            return i + (price - lo) / (hi - lo) - 0.5
    return N_PRICE_BINS - 0.5


def spice_block(level: float) -> np.ndarray:
    return soft_bins(level, SPICE_LEVELS.astype(float), config.SPICE_SIGMA)


def price_block(price: float) -> np.ndarray:
    return soft_bins(price_position(price), np.arange(N_PRICE_BINS, dtype=float), config.PRICE_SIGMA)


@dataclass
class FeatureSpace:
    categories: list[str]
    vibes: list[str]

    @property
    def slices(self) -> dict[str, slice]:
        c, v = len(self.categories), len(self.vibes)
        s, p = len(SPICE_LEVELS), N_PRICE_BINS
        return {
            "category": slice(0, c),
            "vibe": slice(c, c + v),
            "spice": slice(c + v, c + v + s),
            "price": slice(c + v + s, c + v + s + p),
            "diet": slice(c + v + s + p, c + v + s + p + 3),
        }

    @property
    def dim(self) -> int:
        return self.slices["diet"].stop

    def _weighted(self, blocks: dict[str, np.ndarray]) -> np.ndarray:
        vec = np.zeros(self.dim)
        for name, sl in self.slices.items():
            vec[sl] = blocks[name] * config.FEATURE_WEIGHTS[name]
        return vec

    # ------------------------------------------------------------ stalls
    def stall_vector(self, s: Stall) -> np.ndarray:
        cat = np.array([1.0 if c == s.category else 0.0 for c in self.categories])
        vib = np.array([1.0 if v in s.vibe_tags else 0.0 for v in self.vibes])
        if vib.any():
            vib /= np.linalg.norm(vib)   # many tags should not outweigh one strong tag
        diet = np.array([
            1.0 if s.veg_type in ("veg", "both") else 0.0,      # serves veg
            1.0 if s.veg_type in ("non_veg", "both") else 0.0,  # serves non-veg
            1.0 if s.jain_options else 0.0,
        ])
        return self._weighted({
            "category": cat, "vibe": vib,
            "spice": spice_block(s.spice_level),
            "price": price_block(s.price_per_person_inr),
            "diet": diet,
        })

    def stall_matrix(self, stalls: list[Stall]) -> np.ndarray:
        return np.vstack([self.stall_vector(s) for s in stalls]) if stalls else np.zeros((0, self.dim))

    # ------------------------------------------------------------ intent
    def intent_vector(self, p: Preferences) -> np.ndarray:
        wanted = set(p.include_categories)
        cat = np.array([1.0 if c in wanted else 0.0 for c in self.categories])
        if cat.any():
            cat /= np.linalg.norm(cat)
        vib = np.array([1.0 if v in p.vibes else 0.0 for v in self.vibes])
        if vib.any():
            vib /= np.linalg.norm(vib)
        diet = {
            "veg": np.array([1.0, 0.0, 0.0]),
            "jain": np.array([1.0, 0.0, 1.0]),
            "non_veg": np.array([0.0, 1.0, 0.0]),
            "any": np.zeros(3),
        }[p.diet]
        # no spice or budget preference -> those blocks stay zero and do not affect the match
        spice = spice_block(p.spice_target) if p.spice_target else np.zeros(len(SPICE_LEVELS))
        price = price_block(p.budget_total_inr / max(p.stops, 1)) if p.budget_total_inr else np.zeros(N_PRICE_BINS)
        return self._weighted({"category": cat, "vibe": vib, "spice": spice, "price": price, "diet": diet})

    def profile_preferences(self, u: User, area: str | None = None) -> Preferences:
        """Turn a stored user profile into Preferences (used by the evaluation)."""
        return Preferences(
            area=area or u.home_area,
            diet=u.diet,
            spice_target=u.spice_tolerance,
            spice_max=5,
            budget_total_inr=u.budget_per_person_inr,
            stops=4,
            include_categories=[c for c in u.favourite_categories if c in self.categories],
        )
