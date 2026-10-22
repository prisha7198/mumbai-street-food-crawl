"""Route builder: a small Orienteering Problem.

Orienteering (see Gavalas et al., 2014): every stall has a score, walking
costs distance, and there is a total walking budget. Choose N stops and an
order that collect as much score as possible without blowing the budget.

The exact problem is NP-hard, so we use the classic two-step heuristic:

1. Greedy construction. Stand at the area centre. Repeatedly walk to the
   candidate with the best  value - alpha * walk_km  that still fits in the
   remaining walking budget. Stop at N stops or when nothing fits.
2. 2-opt improvement. Try reversing every segment of the route; keep any
   reversal that makes the total walk shorter. Repeat until nothing improves.
   2-opt only reorders, so it can never push the route over budget.

The walking budget covers the walk between stops. Getting to the first stop
(you arrive by train, cab or on foot from the area centre) is not counted
against it, but it is still charged in the greedy value so the crawl starts
near the centre.

To keep the variety MMR just bought, the greedy value also subtracts MMR's
redundancy term:

    value = lambda * score - (1 - lambda) * max_sim(candidate, stops so far)

If the user wants to end on something sweet, a dessert stall is held back
for the last slot, and every earlier choice must leave a dessert reachable.
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import config
from ..geo import walk_km, walk_minutes

Point = tuple[float, float]


@dataclass
class Candidate:
    id: str
    lat: float
    lng: float
    score: float
    is_dessert: bool = False

    @property
    def pt(self) -> Point:
        return (self.lat, self.lng)


def _d(a: Point, b: Point) -> float:
    return walk_km(a[0], a[1], b[0], b[1])


def path_length(stops: list[Candidate]) -> float:
    """Walking between consecutive stops (the part the budget covers)."""
    return sum(_d(stops[i].pt, stops[i + 1].pt) for i in range(len(stops) - 1))


def two_opt(stops: list[Candidate], fix_last: bool = False) -> list[Candidate]:
    """2-opt on an open path. Optionally keeps the last stop in place."""
    route = list(stops)
    n = len(route)
    hi = n - 2 if fix_last else n - 1          # last index that may move
    if hi < 1:
        return route

    def d(a: int, b: int) -> float:
        return _d(route[a].pt, route[b].pt)

    improved = True
    while improved:
        improved = False
        for i in range(0, hi):
            for j in range(i + 1, hi + 1):
                # reversing route[i..j] replaces edges (i-1, i) and (j, j+1) with (i-1, j) and (i, j+1);
                # an edge that would hang off either end of the path does not exist
                before = (d(i - 1, i) if i > 0 else 0.0) + (d(j, j + 1) if j + 1 < n else 0.0)
                after = (d(i - 1, j) if i > 0 else 0.0) + (d(i, j + 1) if j + 1 < n else 0.0)
                if after < before - 1e-9:
                    route[i:j + 1] = reversed(route[i:j + 1])
                    improved = True
    return route


def build_route(
    start: Point,
    candidates: list[Candidate],
    n: int,
    budget_km: float,
    alpha: float = config.ROUTE_ALPHA,
    end_with_dessert: bool = False,
    pinned_ids: list[str] | None = None,
    similarity=None,
    lam: float = config.MMR_LAMBDA,
) -> dict:
    """similarity: optional callable (id_a, id_b) -> cosine similarity of two stalls."""
    by_id = {c.id: c for c in candidates}
    pinned = [by_id[p] for p in (pinned_ids or []) if p in by_id][:n]
    trace: dict = {"alpha": alpha, "budget_km": budget_km, "pool": len(candidates),
                   "pinned": [c.id for c in pinned], "dessert_forced": False, "steps": [],
                   "redundancy_term": similarity is not None}

    want_dessert = end_with_dessert and n >= 2
    pinned_dessert = next((c for c in pinned if c.is_dessert), None) if want_dessert else None
    desserts = [c for c in candidates if c.is_dessert and c not in pinned]
    hold_dessert = want_dessert and pinned_dessert is None and bool(desserts)

    def value(c: Candidate, picked: list[Candidate]) -> float:
        if similarity is None:
            return c.score
        redundancy = max((similarity(c.id, o.id) for o in picked), default=0.0)
        return lam * c.score - (1 - lam) * redundancy

    def leg_cost(pos: Point | None, c: Candidate) -> tuple[float, float]:
        """(km charged to the budget, km used in the greedy value)."""
        if pos is None:                         # first stop: walk from the centre is free
            return 0.0, _d(start, c.pt)
        km = _d(pos, c.pt)
        return km, km

    def reach_dessert(frm: Point, exclude: set[str]) -> float:
        opts = [_d(frm, d.pt) for d in desserts if d.id not in exclude]
        return min(opts) if opts else float("inf")

    # ---- pinned stops first, ordered nearest-neighbour from the start
    chosen: list[Candidate] = []
    pos: Point | None = None
    total = 0.0
    rest = [c for c in pinned if c is not pinned_dessert]
    while rest:
        nxt = min(rest, key=lambda c: _d(pos or start, c.pt))
        total += leg_cost(pos, nxt)[0]
        pos = nxt.pt
        chosen.append(nxt)
        rest.remove(nxt)

    slots = n - (1 if (hold_dessert or pinned_dessert) else 0)
    pool = [c for c in candidates if c not in pinned and not (hold_dessert and c.is_dessert)]

    # ---- greedy construction
    stop_reason = None
    while len(chosen) < slots:
        best, best_val, best_budget_km, best_km = None, float("-inf"), 0.0, 0.0
        taken = {c.id for c in chosen}
        for c in pool:
            if c.id in taken:
                continue
            budget_km_used, km = leg_cost(pos, c)
            reserve = reach_dessert(c.pt, taken | {c.id}) if hold_dessert else 0.0
            if total + budget_km_used + reserve > budget_km + 1e-9:
                continue
            val = value(c, chosen) - alpha * km
            if val > best_val:
                best, best_val, best_budget_km, best_km = c, val, budget_km_used, km
        if best is None:
            stop_reason = "walk_budget" if any(c.id not in taken for c in pool) else "candidates"
            break
        chosen.append(best)
        total += best_budget_km
        pos = best.pt
        trace["steps"].append({"id": best.id, "walk_km": round(best_km, 3), "value": round(best_val, 4)})

    # ---- dessert last
    if pinned_dessert is not None:
        chosen.append(pinned_dessert)
        trace["dessert_forced"] = True
    elif hold_dessert:
        taken = {c.id for c in chosen}
        options = []
        for d in desserts:
            if d.id in taken:
                continue
            budget_km_used, km = leg_cost(pos, d)
            if total + budget_km_used <= budget_km + 1e-9:
                options.append((value(d, chosen) - alpha * km, d, km))
        if options:
            val, d, km = max(options, key=lambda t: t[0])
            chosen.append(d)
            trace["dessert_forced"] = True
            trace["steps"].append({"id": d.id, "walk_km": round(km, 3), "value": round(val, 4)})
        else:
            trace["dessert_unavailable"] = True

    # ---- 2-opt, then start from whichever end is nearer the centre
    greedy_km = path_length(chosen)
    ordered = two_opt(chosen, fix_last=trace["dessert_forced"])
    if (not trace["dessert_forced"] and len(ordered) > 1
            and _d(start, ordered[-1].pt) < _d(start, ordered[0].pt)):
        ordered.reverse()                       # same length, nearer start
    final_km = path_length(ordered)

    legs = []
    prev = start
    for k, c in enumerate(ordered):
        km = _d(prev, c.pt)
        legs.append({"id": c.id, "walk_km": km, "walk_m": int(round(km * 1000)), "walk_min": walk_minutes(km),
                     "from": "centre" if k == 0 else "previous"})
        prev = c.pt

    trace.update({
        "greedy_km": round(greedy_km, 3),
        "two_opt_km": round(final_km, 3),
        "two_opt_saved_m": int(round((greedy_km - final_km) * 1000)),
        "greedy_order": [c.id for c in chosen],
        "final_order": [c.id for c in ordered],
        "stop_reason": stop_reason,
    })
    return {"order": [c.id for c in ordered], "legs": legs, "total_km": final_km, "trace": trace}
