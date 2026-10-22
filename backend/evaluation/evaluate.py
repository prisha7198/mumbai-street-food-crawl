"""Offline evaluation of the ranking stages.

Protocol
--------
* For every user, hold out 20% of their ratings (fixed seed). The rest is
  the training set; collaborative filtering is re-fit on it.
* Candidates = stalls the user has not rated in training and that pass
  their diet (a veg user is never shown a non-veg stall, for every variant).
* Each variant recommends 10 stalls. A held-out stall counts as relevant
  when the user rated it 4 or 5.
* Metrics: Precision@5, Recall@10, NDCG@10 (binary gain), catalogue
  coverage (share of all stalls that appear in anyone's top 10) and
  intra-list similarity (mean pairwise cosine of the top 10; lower = more varied).

Variants
--------
* Popularity: most-reviewed stalls first.
* Content only: cosine between the user's profile vector and each stall.
* CF only: item-based CF prediction.
* Hybrid + MMR: the production blend (0.45 / 0.30 / 0.25) then MMR, lambda 0.7.

Run from /backend:  python -m evaluation.evaluate
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.data_loader import load_dataset  # noqa: E402
from app.recommender.collaborative import ItemCF  # noqa: E402
from app.recommender.content import content_scores  # noqa: E402
from app.recommender.diversity import intra_list_similarity, mmr, similarity_matrix  # noqa: E402
from app.recommender.features import FeatureSpace  # noqa: E402
from app.recommender.filters import diet_ok  # noqa: E402
from app.recommender.hybrid import minmax  # noqa: E402
from app.recommender.quality import bayesian_params, quality_scores  # noqa: E402

SEED = 42
HOLDOUT = 0.2
K_PREC, K = 5, 10
RELEVANT = 4
REPORT = Path(__file__).resolve().parent / "report.md"


def split(ratings: pd.DataFrame, rng: random.Random) -> tuple[pd.DataFrame, pd.DataFrame]:
    train, test = [], []
    for _, grp in ratings.groupby("user_id", sort=True):
        rows = grp.sort_values("stall_id").to_dict("records")
        rng.shuffle(rows)
        n_test = max(1, round(len(rows) * HOLDOUT))
        test += rows[:n_test]
        train += rows[n_test:]
    return pd.DataFrame(train), pd.DataFrame(test)


def precision_at(rec: list[str], rel: set[str], k: int) -> float:
    return sum(1 for s in rec[:k] if s in rel) / k


def recall_at(rec: list[str], rel: set[str], k: int) -> float:
    return sum(1 for s in rec[:k] if s in rel) / len(rel)


def ndcg_at(rec: list[str], rel: set[str], k: int) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, s in enumerate(rec[:k]) if s in rel)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return dcg / ideal


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    rng = random.Random(SEED)

    ds = load_dataset(verbose=False)
    stalls = ds.stalls
    ids = [s.id for s in stalls]
    pos = {sid: i for i, sid in enumerate(ids)}
    space = FeatureSpace(ds.categories, ds.vibes)
    X = space.stall_matrix(stalls)
    C, m = bayesian_params(stalls)
    quality = quality_scores(stalls, C, m)
    popularity = np.array([s.review_count for s in stalls], dtype=float)

    ratings = pd.DataFrame([r.model_dump() for r in ds.ratings])
    train, test = split(ratings, rng)
    cf = ItemCF(train, ids)

    variants = ["Popularity", "Content only", "CF only", "Hybrid + MMR"]
    results = {v: {"p5": [], "r10": [], "ndcg": [], "ils": [], "items": set()} for v in variants}
    users_evaluated = 0

    for u in ds.users:
        test_u = test[test["user_id"] == u.user_id]
        relevant = set(test_u.loc[test_u["rating"] >= RELEVANT, "stall_id"])
        seen = set(train.loc[train["user_id"] == u.user_id, "stall_id"])
        cand = [i for i, s in enumerate(stalls) if s.id not in seen and diet_ok(s, u.diet)]
        if not cand:
            continue

        # profile vector: what they told us + what they liked in training (classic content-based profile)
        intent = space.intent_vector(space.profile_preferences(u))
        liked = [pos[s] for s in train.loc[(train["user_id"] == u.user_id) & (train["rating"] >= RELEVANT), "stall_id"]]
        if liked:
            taste = X[liked].mean(axis=0)
            intent = intent / (np.linalg.norm(intent) or 1) + taste / (np.linalg.norm(taste) or 1)
        content = content_scores(intent, X[cand])
        cf_pred = cf.predict_many(u.user_id, [ids[i] for i in cand])

        def top(scores: np.ndarray) -> list[int]:
            return [cand[i] for i in np.argsort(-scores, kind="stable")[:K]]

        w = config.HYBRID_WEIGHTS
        hybrid = w["content"] * minmax(content) + w["quality"] * minmax(quality[cand]) + w["cf"] * minmax(cf_pred)
        order = np.argsort(-hybrid, kind="stable")[: config.MMR_POOL]
        picked = mmr(hybrid[order], similarity_matrix(X[[cand[i] for i in order]]), K)
        hybrid_list = [cand[order[i]] for i in picked]

        lists = {
            "Popularity": top(popularity[cand]),
            "Content only": top(content),
            "CF only": top(cf_pred),
            "Hybrid + MMR": hybrid_list,
        }
        for v, rec_idx in lists.items():
            results[v]["items"].update(rec_idx)
            results[v]["ils"].append(intra_list_similarity(X[rec_idx]))
        if not relevant:
            continue                       # ranking metrics need at least one relevant held-out stall
        users_evaluated += 1
        for v, rec_idx in lists.items():
            rec = [ids[i] for i in rec_idx]
            results[v]["p5"].append(precision_at(rec, relevant, K_PREC))
            results[v]["r10"].append(recall_at(rec, relevant, K))
            results[v]["ndcg"].append(ndcg_at(rec, relevant, K))

    rows = []
    for v in variants:
        r = results[v]
        rows.append({
            "Variant": v,
            "Precision@5": float(np.mean(r["p5"])),
            "Recall@10": float(np.mean(r["r10"])),
            "NDCG@10": float(np.mean(r["ndcg"])),
            "Coverage": len(r["items"]) / len(stalls),
            "Intra-list sim.": float(np.mean(r["ils"])),
        })
    table = pd.DataFrame(rows)
    density = len(ratings) / (len(ds.users) * len(stalls))
    write_report(table, users_evaluated, len(ds.users), len(train), len(test), len(stalls), density)
    print(table.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print(f"\nWrote {REPORT}")


def write_report(t: pd.DataFrame, n_eval: int, n_users: int, n_train: int, n_test: int, n_stalls: int,
                 density: float) -> None:
    by = t.set_index("Variant")
    best_ndcg = by["NDCG@10"].idxmax()
    pop, hyb, cfo, con = (by.loc[v] for v in ("Popularity", "Hybrid + MMR", "CF only", "Content only"))

    def pct(a: float, b: float) -> str:
        return f"{(a - b) / b * 100:+.0f}%" if b else "n/a"

    s1 = (f"{best_ndcg} has the best NDCG@10 ({by.loc[best_ndcg, 'NDCG@10']:.3f}); the full hybrid scores "
          f"{hyb['NDCG@10']:.3f}, {pct(hyb['NDCG@10'], pop['NDCG@10'])} against the popularity baseline "
          f"({pop['NDCG@10']:.3f}).")
    if cfo["NDCG@10"] < 1.5 * pop["NDCG@10"]:
        s2 = (f"CF on its own ({cfo['NDCG@10']:.3f}) barely beats popularity because the rating matrix is only "
              f"{density:.0%} full, so item neighbourhoods are noisy; that is why it gets the smallest weight "
              f"and is only switched on when a profile is chosen.")
    else:
        s2 = (f"CF on its own reaches {cfo['NDCG@10']:.3f} and content on its own {con['NDCG@10']:.3f}; they "
              f"capture different signals (co-rating patterns versus stated taste), which is why they are blended.")
    if hyb["NDCG@10"] < con["NDCG@10"]:
        s3 = (f"Hybrid + MMR gives up {abs((hyb['NDCG@10'] - con['NDCG@10']) / con['NDCG@10']):.0%} of content-only's "
              f"NDCG in exchange for a clearly more varied list (intra-list similarity {hyb['Intra-list sim.']:.3f} "
              f"versus {con['Intra-list sim.']:.3f}), the accuracy-diversity trade-off MMR is designed to make "
              f"for a crawl, where five near-identical stalls would be a poor evening.")
    else:
        s3 = (f"MMR keeps the hybrid list varied (intra-list similarity {hyb['Intra-list sim.']:.3f} versus "
              f"{con['Intra-list sim.']:.3f} for content-only) without losing accuracy.")

    header = "| Variant | Precision@5 | Recall@10 | NDCG@10 | Coverage | Intra-list sim. |\n|---|---:|---:|---:|---:|---:|\n"
    body = "".join(
        f"| {r['Variant']} | {r['Precision@5']:.3f} | {r['Recall@10']:.3f} | {r['NDCG@10']:.3f} | "
        f"{r['Coverage']:.1%} | {r['Intra-list sim.']:.3f} |\n" for _, r in t.iterrows())
    REPORT.write_text(
        "# Offline evaluation\n\n"
        f"Seed {SEED}. {n_users} users, {n_stalls} stalls. 20% of each user's ratings held out "
        f"({n_train} train / {n_test} test; the rating matrix is {density:.1%} full). Relevant = held-out rating of {RELEVANT} or 5. "
        f"Ranking metrics are averaged over the {n_eval} users with at least one relevant held-out stall; "
        "coverage and intra-list similarity use every user. Candidates exclude stalls the user rated in "
        "training and stalls that break their diet.\n\n"
        + header + body +
        "\n## What this says\n\n" + f"{s1} {s2} {s3}\n\n"
        "## Notes\n\n"
        "- Precision is bounded by how few stalls each user rated: an unrated stall counts as not relevant, "
        "even if the user might love it, so absolute numbers are low for every variant and only the "
        "comparison between rows is meaningful.\n"
        "- Lower intra-list similarity means a more varied list (Ziegler et al., 2005).\n"
        "- Re-run with `python -m evaluation.evaluate` from `/backend`; results are deterministic.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
