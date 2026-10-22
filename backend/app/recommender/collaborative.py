"""Item-based collaborative filtering.

1. Build a user x stall rating matrix from ratings.json.
2. Mean-centre each user's ratings (a 3 from a harsh rater means more than
   a 3 from someone who gives everything a 5).
3. Similarity between two stalls = cosine of their centred rating columns.
4. To predict user u's rating for stall i, take the k = 10 stalls most
   similar to i that u has rated, and average u's centred ratings for them,
   weighted by similarity. Add u's mean back.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from .. import config


class ItemCF:
    def __init__(self, ratings: pd.DataFrame, stall_ids: list[str], k: int = config.CF_K):
        """ratings: DataFrame with columns user_id, stall_id, rating."""
        self.k = k
        self.stall_ids = list(stall_ids)
        self.col = {sid: j for j, sid in enumerate(self.stall_ids)}
        df = ratings[ratings["stall_id"].isin(self.col)]
        # if a user rated the same stall twice, keep the average
        df = df.groupby(["user_id", "stall_id"], as_index=False)["rating"].mean()

        self.user_ids = sorted(df["user_id"].unique())
        self.row = {u: i for i, u in enumerate(self.user_ids)}
        R = np.full((len(self.user_ids), len(self.stall_ids)), np.nan)
        for u, s, r in df[["user_id", "stall_id", "rating"]].itertuples(index=False):
            R[self.row[u], self.col[s]] = r
        self.R = R
        self.rated = ~np.isnan(R)
        with np.errstate(invalid="ignore"):
            self.user_mean = np.where(self.rated.any(1), np.nanmean(np.where(self.rated, R, np.nan), axis=1), 3.0)
        centred = np.where(self.rated, R - self.user_mean[:, None], 0.0)
        self.centred = centred
        # item x item cosine similarity on centred columns
        self.sim = cosine_similarity(centred.T) if len(self.user_ids) else np.zeros((len(stall_ids),) * 2)
        np.fill_diagonal(self.sim, 0.0)

    def has_user(self, user_id: str) -> bool:
        return user_id in self.row

    def predict(self, user_id: str, stall_id: str) -> tuple[float, int]:
        """(predicted rating on 1..5, number of neighbours used)."""
        if user_id not in self.row or stall_id not in self.col:
            return 3.0, 0
        u, i = self.row[user_id], self.col[stall_id]
        if self.rated[u, i]:
            return float(self.R[u, i]), -1     # already rated: return the real rating
        rated_j = np.where(self.rated[u])[0]
        if rated_j.size == 0:
            return float(self.user_mean[u]), 0
        sims = self.sim[i, rated_j]
        positive = sims > 0
        rated_j, sims = rated_j[positive], sims[positive]
        if rated_j.size == 0:
            return float(self.user_mean[u]), 0
        top = np.argsort(-sims)[: self.k]
        rated_j, sims = rated_j[top], sims[top]
        pred = self.user_mean[u] + (sims @ self.centred[u, rated_j]) / sims.sum()
        return float(np.clip(pred, 1.0, 5.0)), int(rated_j.size)

    def predict_many(self, user_id: str, stall_ids: list[str]) -> np.ndarray:
        return np.array([self.predict(user_id, s)[0] for s in stall_ids])

    def rated_by(self, user_id: str) -> set[str]:
        if user_id not in self.row:
            return set()
        return {self.stall_ids[j] for j in np.where(self.rated[self.row[user_id]])[0]}
