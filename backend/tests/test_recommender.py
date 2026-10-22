import numpy as np
import pytest

from app.hours import is_open, session_day
from app.models import Preferences
from app.recommender.diversity import intra_list_similarity, mmr
from app.recommender.filters import apply_filters, diet_ok, make_context
from app.recommender.quality import bayesian_average, bayesian_params
from app.recommender.routing import Candidate, build_route, path_length


# ---------------------------------------------------------------- opening hours
class TestMidnightHours:
    def test_open_before_midnight(self, stall_factory):
        s = stall_factory(open_time="18:00", close_time="02:30")
        assert is_open(s, 23 * 60, "Monday")

    def test_open_after_midnight(self, stall_factory):
        s = stall_factory(open_time="18:00", close_time="02:30")
        assert is_open(s, 1 * 60 + 15, "Tuesday")

    def test_closed_at_closing_time_and_in_the_gap(self, stall_factory):
        s = stall_factory(open_time="18:00", close_time="02:30")
        assert not is_open(s, 2 * 60 + 30, "Tuesday")
        assert not is_open(s, 12 * 60, "Tuesday")

    def test_after_midnight_belongs_to_previous_days_session(self, stall_factory):
        # closed on Tuesdays: Monday night's session still runs into Tuesday 01:00
        s = stall_factory(open_time="18:00", close_time="02:30", closed_day="Tuesday")
        assert session_day(s, 60, "Tuesday") == "Monday"
        assert is_open(s, 60, "Tuesday")
        # but there is no Tuesday evening session, so Wednesday 01:00 is closed
        assert not is_open(s, 23 * 60, "Tuesday")
        assert not is_open(s, 60, "Wednesday")

    def test_same_day_window(self, stall_factory):
        s = stall_factory(open_time="07:00", close_time="14:00")
        assert is_open(s, 8 * 60, "Friday")
        assert not is_open(s, 15 * 60, "Friday")


# ---------------------------------------------------------------- diet
class TestDietFilter:
    def test_jain_only_sees_jain_options(self, stall_factory):
        assert diet_ok(stall_factory(veg_type="veg", jain_options=True), "jain")
        assert not diet_ok(stall_factory(veg_type="veg", jain_options=False), "jain")

    def test_veg_never_sees_non_veg(self, stall_factory):
        assert diet_ok(stall_factory(veg_type="veg"), "veg")
        assert diet_ok(stall_factory(veg_type="both"), "veg")
        assert not diet_ok(stall_factory(veg_type="non_veg"), "veg")

    def test_filter_on_real_data(self):
        from app.data_loader import get_dataset
        ds = get_dataset()
        for diet in ("veg", "jain"):
            p = Preferences(area="Ghatkopar", diet=diet, time="20:00", max_walk_km=10)
            a = ds.areas["Ghatkopar"]
            kept, trace = apply_filters(ds.stalls, p, make_context(p, (a["lat"], a["lng"])))
            assert kept, "expected some stalls to survive"
            assert all(s.veg_type != "non_veg" for s in kept)
            if diet == "jain":
                assert all(s.jain_options for s in kept)
            assert sum(st["removed"] for st in trace["steps"]) == trace["start"] - trace["remaining"]


# ---------------------------------------------------------------- Bayesian average
class TestBayesian:
    def test_formula(self):
        # v = m: halfway between the stall's rating and the global mean
        assert bayesian_average(R=5.0, v=100, C=4.0, m=100) == pytest.approx(4.5)

    def test_few_reviews_pulled_to_mean(self):
        few = bayesian_average(R=4.9, v=5, C=4.0, m=200)
        many = bayesian_average(R=4.6, v=3000, C=4.0, m=200)
        assert few < many
        assert 4.0 < few < 4.1

    def test_params(self, stall_factory):
        stalls = [stall_factory(id=f"s{i}", rating=r, review_count=c)
                  for i, (r, c) in enumerate([(4.0, 10), (5.0, 20), (3.0, 30), (4.0, 40), (4.0, 50)])]
        C, m = bayesian_params(stalls, percentile=60)
        assert C == pytest.approx(4.0)
        assert m == pytest.approx(np.percentile([10, 20, 30, 40, 50], 60))


# ---------------------------------------------------------------- MMR
class TestMMR:
    def test_mmr_changes_order_when_duplicates_exist(self):
        # items 0, 1, 2 are near-identical (three vada pav stalls); 3 is different
        vecs = np.array([[1, 0, 0], [1, 0.01, 0], [1, 0, 0.01], [0, 1, 0]], dtype=float)
        sim = vecs @ vecs.T / np.outer(np.linalg.norm(vecs, axis=1), np.linalg.norm(vecs, axis=1))
        relevance = np.array([0.95, 0.94, 0.93, 0.80])
        plain = list(np.argsort(-relevance))
        diverse = mmr(relevance, sim, 4, lam=0.7)
        assert plain[:3] == [0, 1, 2]
        assert diverse != plain
        assert diverse[1] == 3, "the different item should jump to second place"
        assert intra_list_similarity(vecs[diverse[:2]]) < intra_list_similarity(vecs[plain[:2]])

    def test_lambda_one_is_pure_relevance(self):
        sim = np.ones((3, 3))
        rel = np.array([0.2, 0.9, 0.5])
        assert mmr(rel, sim, 3, lam=1.0) == [1, 2, 0]


# ---------------------------------------------------------------- routing
def _grid_candidates(seed: int, n: int = 30):
    rng = np.random.default_rng(seed)
    return [Candidate(id=f"c{i}", lat=19.02 + rng.normal(0, 0.008), lng=72.84 + rng.normal(0, 0.008),
                      score=float(rng.random()), is_dessert=i % 7 == 0) for i in range(n)]


class TestRouting:
    @pytest.mark.parametrize("seed", range(25))
    @pytest.mark.parametrize("budget", [0.5, 1.0, 2.5])
    def test_route_never_exceeds_walk_budget(self, seed, budget):
        cands = _grid_candidates(seed)
        for dessert in (False, True):
            r = build_route((19.02, 72.84), cands, 5, budget, end_with_dessert=dessert)
            stops = [next(c for c in cands if c.id == i) for i in r["order"]]
            assert path_length(stops) <= budget + 1e-6
            assert r["total_km"] <= budget + 1e-6
            assert len(r["order"]) <= 5

    def test_dessert_is_last(self):
        cands = _grid_candidates(3)
        r = build_route((19.02, 72.84), cands, 4, 5.0, end_with_dessert=True)
        last = next(c for c in cands if c.id == r["order"][-1])
        assert last.is_dessert

    def test_two_opt_never_makes_it_longer(self):
        for seed in range(10):
            r = build_route((19.02, 72.84), _grid_candidates(seed), 6, 10.0)
            assert r["trace"]["two_opt_km"] <= r["trace"]["greedy_km"] + 1e-9

    def test_pinned_stops_are_kept(self):
        cands = _grid_candidates(5)
        r = build_route((19.02, 72.84), cands, 4, 10.0, pinned_ids=["c3", "c9"])
        assert {"c3", "c9"} <= set(r["order"])
