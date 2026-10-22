# Offline evaluation

Seed 42. 48 users, 172 stalls. 20% of each user's ratings held out (1261 train / 317 test; the rating matrix is 19.1% full). Relevant = held-out rating of 4 or 5. Ranking metrics are averaged over the 47 users with at least one relevant held-out stall; coverage and intra-list similarity use every user. Candidates exclude stalls the user rated in training and stalls that break their diet.

| Variant | Precision@5 | Recall@10 | NDCG@10 | Coverage | Intra-list sim. |
|---|---:|---:|---:|---:|---:|
| Popularity | 0.034 | 0.090 | 0.057 | 20.9% | 0.442 |
| Content only | 0.098 | 0.217 | 0.157 | 86.6% | 0.629 |
| CF only | 0.038 | 0.092 | 0.060 | 88.4% | 0.465 |
| Hybrid + MMR | 0.064 | 0.213 | 0.139 | 69.2% | 0.484 |

## What this says

Content only has the best NDCG@10 (0.157); the full hybrid scores 0.139, +145% against the popularity baseline (0.057). CF on its own (0.060) barely beats popularity because the rating matrix is only 19% full, so item neighbourhoods are noisy; that is why it gets the smallest weight and is only switched on when a profile is chosen. Hybrid + MMR gives up 12% of content-only's NDCG in exchange for a clearly more varied list (intra-list similarity 0.484 versus 0.629), the accuracy-diversity trade-off MMR is designed to make for a crawl, where five near-identical stalls would be a poor evening.

## Notes

- Precision is bounded by how few stalls each user rated: an unrated stall counts as not relevant, even if the user might love it, so absolute numbers are low for every variant and only the comparison between rows is meaningful.
- Lower intra-list similarity means a more varied list (Ziegler et al., 2005).
- Re-run with `python -m evaluation.evaluate` from `/backend`; results are deterministic.
