"""Build the notice shown when fewer stops fit than were asked for.

For each constraint we loosen it on its own (budget up, walk radius up,
spice cap removed, a different time, a nearby area, no skipped categories),
count how many stops would then fit, and suggest the single change that
recovers the most. If no single change helps, we try pairs.
"""
from __future__ import annotations

import math
from itertools import combinations

from .. import config
from ..geo import haversine_km
from ..models import Preferences

PRIORITY = ["budget", "walk", "spice", "category", "time", "area"]   # least to most disruptive


def _fmt_time(hhmm: str) -> str:
    h, m = map(int, hhmm.split(":"))
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}" if m else f"{h12} {suffix}"


def _round_up(x: float, step: int = 50) -> int:
    return int(math.ceil(x / step) * step)


def _variants(engine, p: Preferences, minutes_now: int) -> dict[str, list[tuple[dict, str]]]:
    """dimension -> list of (patch, label), ordered from smallest change to largest."""
    out: dict[str, list[tuple[dict, str]]] = {}
    if p.budget_total_inr:
        budgets = {_round_up(p.budget_total_inr * f) for f in config.RELAX_BUDGET_FACTORS}
        budgets |= {p.stops * per for per in config.RELAX_BUDGET_PER_STOP}
        out["budget"] = [({"budget_total_inr": b}, f"raise the budget to ₹{b}") for b in sorted(budgets)
                         if p.budget_total_inr < b <= 20_000]
    out["walk"] = [({"max_walk_km": km}, f"allow up to {km:g} km of walking")
                   for km in config.RELAX_WALK_KM if km > p.max_walk_km]
    out["spice"] = [({"spice_max": 5}, "allow spice up to 5/5")] if p.spice_max < 5 else []
    if p.exclude_categories:
        out["category"] = [({"exclude_categories": []}, "stop skipping categories")]

    def circ(t: str) -> int:
        mins = int(t[:2]) * 60 + int(t[3:])
        d = abs(mins - minutes_now)
        return min(d, 1440 - d)
    times = sorted((t for t in config.RELAX_TIMES if t != p.time), key=circ)
    out["time"] = [({"time": t}, f"go at {_fmt_time(t)} instead") for t in times]

    here = engine.centre(p.area)
    others = sorted((a for a in engine.ds.areas if a != p.area),
                    key=lambda a: haversine_km(*here, *engine.centre(a)))[:3]
    out["area"] = [({"area": a}, f"try {a} instead") for a in others]
    return out


def _upper_bound(engine, p: Preferences, patch: dict, exclude_ids) -> int:
    """Stops that could fit if walking were free: a cheap filter-only count."""
    q = p.model_copy(update=patch)
    return min(q.stops, engine.count_candidates(q, exclude_ids))


def _count(engine, p: Preferences, patch: dict, exclude_ids, pinned_ids=()) -> int:
    """Stops that actually fit: filters plus the route builder."""
    if _upper_bound(engine, p, patch, exclude_ids) == 0:
        return 0
    q = p.model_copy(update=patch)
    return len(engine.plan(q, None, exclude_ids, pinned_ids, fast=True)["route"]["order"])


def _headline(p: Preferences, got: int, ftrace: dict, filtered_count: int) -> str:
    removed = {s["rule"]: s["removed"] for s in ftrace["steps"]}
    noun = {"veg": "veg stalls", "jain": "Jain friendly stalls", "non_veg": "non-veg stalls",
            "any": "stalls"}[p.diet]
    if filtered_count >= p.stops:
        # enough stalls exist, the walk budget is what cut the list short
        return f"Only {got} stop{'s' if got != 1 else ''} fit in a {p.max_walk_km:g} km walk around {p.area}."
    count = filtered_count
    if count == 0:
        head = f"No {noun} are"
    elif count == 1:
        head = f"Only 1 {noun[:-1]} is"
    else:
        head = f"Only {count} {noun} are"
    when = _fmt_time(ftrace["time"])
    parts = [head]
    if removed.get("hours") or removed.get("closed_day"):
        parts.append("open")
    parts.append(f"near {p.area}")
    if removed.get("hours") or removed.get("closed_day"):
        parts.append(f"at {when}")
    if removed.get("price"):
        parts.append(f"under ₹{ftrace['per_stop_cap']} a stop")
    if removed.get("spice"):
        parts.append(f"within spice {p.spice_max}/5")
    return " ".join(parts) + "."


def build_notice(engine, p: Preferences, got: int, ftrace: dict, filtered_count: int,
                 requested_stops: int | None, minutes_now: int, profile_id=None, exclude_ids=(),
                 pinned_ids=()) -> dict | None:
    capped = requested_stops is not None and requested_stops > config.MAX_STOPS
    cap_note = f"Crawls top out at {config.MAX_STOPS} stops." if capped else ""
    if got >= p.stops:
        if capped:
            return {"kind": "info", "message": f"{cap_note} Here are the best {config.MAX_STOPS}.",
                    "action": None, "bottleneck": "stops_cap"}
        return None

    variants = _variants(engine, p, minutes_now)
    best_per_dim: dict[str, tuple[int, dict, str]] = {}
    for dim, opts in variants.items():
        best = None
        for patch, label in opts:
            c = _count(engine, p, patch, exclude_ids, pinned_ids)
            if best is None or c > best[0]:
                best = (c, patch, label)
            if c >= p.stops:
                break                         # smallest change that fully fixes it
        if best:
            best_per_dim[dim] = best

    choice = None
    for dim in PRIORITY:
        if dim in best_per_dim and (choice is None or best_per_dim[dim][0] > choice[0]):
            choice = (best_per_dim[dim][0], best_per_dim[dim][1], [best_per_dim[dim][2]], [dim])

    if choice is None or choice[0] <= got:
        # no single change helps: try two changes together
        pair_best = None
        for d1, d2 in combinations([d for d in PRIORITY if d in variants], 2):
            for patch1, label1 in variants[d1]:
                for patch2, label2 in variants[d2]:
                    patch = {**patch1, **patch2}
                    if _upper_bound(engine, p, patch, exclude_ids) <= (pair_best[0] if pair_best else got):
                        continue                  # cannot beat what we already have
                    c = _count(engine, p, patch, exclude_ids, pinned_ids)
                    if pair_best is None or c > pair_best[0]:
                        pair_best = (c, {**patch1, **patch2}, [label1, label2], [d1, d2])
                    if c >= p.stops:
                        break
                if pair_best and pair_best[0] >= p.stops:
                    break
            if pair_best and pair_best[0] >= p.stops:
                break
        if pair_best and pair_best[0] > got:
            choice = pair_best

    headline = _headline(p, got, ftrace, filtered_count)
    if cap_note:
        headline = f"{cap_note} {headline}"
    if choice is None or choice[0] <= got:
        return {"kind": "empty" if got == 0 else "short",
                "message": headline + " Try another area or time of day.",
                "action": None, "bottleneck": None}

    m = choice[0]
    labels = [l.replace(" instead", "") for l in choice[2]] if len(choice[2]) > 1 else choice[2]
    fix = " and ".join(labels)
    fix = fix[0].upper() + fix[1:]
    action_label = labels[0][0].upper() + labels[0][1:] if len(labels) == 1 else fix
    return {
        "kind": "empty" if got == 0 else "short",
        "message": f"{headline} {fix} to get {m} stop{'s' if m != 1 else ''}.",
        "action": {"label": action_label.replace(" instead", ""), "patch": choice[1]},
        "bottleneck": "+".join(choice[3]),
        "recovers": m,
    }
