"""Runs every stage and records what each one did into `trace`.

The Engine is built once at startup: stall vectors, Bayesian parameters and
the item-item similarity matrix do not depend on the request.
"""
from __future__ import annotations

import time
from functools import lru_cache

import numpy as np
import pandas as pd

from .. import config, streets
from ..data_loader import CATEGORY_LABELS, Dataset, get_dataset
from ..hours import status
from ..models import Preferences
from .collaborative import ItemCF
from .content import content_scores
from .diversity import intra_list_similarity, mmr, similarity_matrix
from .features import FeatureSpace
from .filters import apply_filters, make_context
from .hybrid import blend
from .quality import bayesian_params, quality_scores
from .routing import Candidate, build_route


def ratings_frame(ds: Dataset) -> pd.DataFrame:
    return pd.DataFrame([r.model_dump() for r in ds.ratings], columns=["user_id", "stall_id", "rating", "visited_on"])


class Engine:
    def __init__(self, ds: Dataset):
        self.ds = ds
        self.space = FeatureSpace(ds.categories, ds.vibes)
        self.X = self.space.stall_matrix(ds.stalls)
        self.idx = ds.index_of()
        self.C, self.m = bayesian_params(ds.stalls)
        self.quality_raw = quality_scores(ds.stalls, self.C, self.m)
        self.cf = ItemCF(ratings_frame(ds), [s.id for s in ds.stalls])

    # ------------------------------------------------------------ helpers
    def centre(self, area: str) -> tuple[float, float]:
        a = self.ds.areas[area]
        return a["lat"], a["lng"]

    def count_candidates(self, p: Preferences, exclude_ids=()) -> int:
        """Cheap stall count after hard filters (used by the relaxation search)."""
        ctx = make_context(p, self.centre(p.area), exclude_ids)
        remaining, _ = apply_filters(self.ds.stalls, p, ctx)
        return len(remaining)

    # ------------------------------------------------------------ stages 2-5
    def plan(self, p: Preferences, profile_id: str | None = None,
             exclude_ids=(), pinned_ids=(), fast: bool = False) -> dict:
        """fast=True skips MMR and the redundancy term; used only to count how many stops fit."""
        timings = {}
        t0 = time.perf_counter()
        centre = self.centre(p.area)

        # Stage 2: filters
        ctx = make_context(p, centre, exclude_ids)
        filtered, ftrace = apply_filters(self.ds.stalls, p, ctx)
        pinned = [pid for pid in pinned_ids if pid in self.ds.by_id and pid not in set(exclude_ids)]
        kept = {s.id for s in filtered}
        readded = [pid for pid in pinned if pid not in kept]
        filtered = filtered + [self.ds.by_id[pid] for pid in readded]   # pinned stops always stay
        ftrace["pinned_readded"] = readded
        timings["filters"] = time.perf_counter() - t0

        # Stage 3: scoring
        t1 = time.perf_counter()
        rows = [self.idx[s.id] for s in filtered]
        Xc = self.X[rows] if rows else np.zeros((0, self.space.dim))
        intent_vec = self.space.intent_vector(p)
        content = content_scores(intent_vec, Xc)
        quality = self.quality_raw[rows] if rows else np.zeros(0)
        use_cf = bool(profile_id) and self.cf.has_user(profile_id)
        cf = self.cf.predict_many(profile_id, [s.id for s in filtered]) if use_cf else None
        b = blend(content, quality, cf, filtered)
        score = b["score"]
        timings["scoring"] = time.perf_counter() - t1

        # Stage 4: MMR over the top of the hybrid ranking
        t2 = time.perf_counter()
        hybrid_order = list(np.argsort(-score, kind="stable"))
        pool = hybrid_order[: config.MMR_POOL]
        sim_pool = similarity_matrix(Xc[pool]) if pool and not fast else np.zeros((0, 0))
        mmr_local = mmr(score[pool], sim_pool, len(pool)) if pool and not fast else list(range(len(pool)))
        mmr_order = [pool[i] for i in mmr_local]
        n = p.stops
        before_top = hybrid_order[:n]
        after_top = mmr_order[:n]
        div_trace = {
            "lambda": config.MMR_LAMBDA,
            "pool": len(pool),
            "before_ids": [filtered[i].id for i in before_top],
            "after_ids": [filtered[i].id for i in after_top],
            "ils_before": round(intra_list_similarity(Xc[before_top]), 4) if before_top and not fast else 0.0,
            "ils_after": round(intra_list_similarity(Xc[after_top]), 4) if after_top and not fast else 0.0,
        }
        div_trace["changed"] = div_trace["before_ids"] != div_trace["after_ids"]
        div_trace["moved"] = len(set(div_trace["after_ids"]) - set(div_trace["before_ids"]))
        timings["diversity"] = time.perf_counter() - t2

        # Stage 5: route over the diversified shortlist
        t3 = time.perf_counter()
        route_local = mmr_order[: config.ROUTE_POOL]
        for i, s in enumerate(filtered):              # pinned stalls must be in the pool
            if s.id in pinned and i not in route_local:
                route_local.append(i)
        cands = [Candidate(id=filtered[i].id, lat=filtered[i].lat, lng=filtered[i].lng, score=float(score[i]),
                           is_dessert=filtered[i].category in config.DESSERT_CATEGORIES) for i in route_local]
        sim_route = similarity_matrix(Xc[route_local]) if route_local and not fast else np.zeros((0, 0))
        pos_of = {filtered[i].id: k for k, i in enumerate(route_local)}
        route = build_route(centre, cands, n, p.max_walk_km, end_with_dessert=p.end_with_dessert,
                            pinned_ids=pinned,
                            similarity=None if fast else (lambda a, b: float(sim_route[pos_of[a], pos_of[b]])))
        timings["routing"] = time.perf_counter() - t3

        local = {s.id: i for i, s in enumerate(filtered)}
        components = {}
        for sid in set(route["order"]) | set(div_trace["before_ids"]) | set(div_trace["after_ids"]):
            i = local[sid]
            components[sid] = {
                "content": round(float(b["content"][i]), 4),
                "quality": round(float(b["quality"][i]), 4),
                "cf": round(float(b["cf"][i]), 4) if use_cf else None,
                "penalty": round(float(b["penalty"][i]), 4),
                "score": round(float(score[i]), 4),
                "parts": {k: round(float(v[i]), 4) for k, v in b["parts"].items()},
                "raw": {
                    "cosine": round(float(content[i]), 4),
                    "bayesian": round(float(quality[i]), 3),
                    "cf_pred": round(float(cf[i]), 3) if use_cf else None,
                },
            }

        chosen = set(route["order"])
        alternatives = [{
            "id": filtered[i].id, "name": filtered[i].name,
            "category_label": CATEGORY_LABELS.get(filtered[i].category, filtered[i].category),
            "price_per_person_inr": filtered[i].price_per_person_inr, "rating": filtered[i].rating,
            "score": round(float(score[i]), 4),
        } for i in mmr_order if filtered[i].id not in chosen][:5]

        return {
            "route": route,
            "alternatives": alternatives,
            "filtered": filtered,
            "components": components,
            "filters": ftrace,
            "scoring": {
                "weights": {k: round(v, 3) for k, v in b["weights"].items()},
                "cf_active": use_cf,
                "candidates": len(filtered),
                "bayes": {"C": round(self.C, 3), "m": round(self.m, 1)},
            },
            "diversity": div_trace,
            "routing": route["trace"],
            "ctx": ctx,
            "timings_ms": {k: round(v * 1000, 2) for k, v in timings.items()},
        }

    # ------------------------------------------------------------ output shaping
    def stall_out(self, sid: str, minutes: int, day: str) -> dict:
        s = self.ds.by_id[sid]
        d = s.model_dump()
        d["category_label"] = CATEGORY_LABELS.get(s.category, s.category)
        d["status"] = status(s, minutes, day)
        return d

    def assemble(self, plan: dict) -> tuple[list[dict], dict]:
        ctx = plan["ctx"]
        stops = []
        for k, leg in enumerate(plan["route"]["legs"]):
            sid = leg["id"]
            stops.append({
                "order": k + 1,
                "stall": self.stall_out(sid, ctx.minutes, ctx.day),
                "leg": {"walk_km": round(leg["walk_km"], 3), "walk_m": leg["walk_m"],
                        "walk_min": round(leg["walk_min"], 1), "geometry": None, "source": "estimate"},
                "components": plan["components"][sid],
            })
        return stops, self.totals(stops)

    @staticmethod
    def totals(stops: list[dict]) -> dict:
        # walking between stops; the walk to the first stop is not part of the crawl
        between = [s["leg"] for s in stops[1:]]
        walk_m = sum(leg["walk_m"] for leg in between)
        walk_min = sum(leg["walk_min"] for leg in between)
        wait = sum(s["stall"]["avg_wait_minutes"] for s in stops)
        return {
            "stops": len(stops),
            "walk_km": round(walk_m / 1000, 2),
            "walk_m": int(walk_m),
            "walk_min": round(walk_min),
            "cost_inr": sum(s["stall"]["price_per_person_inr"] for s in stops),
            "wait_min": wait,
            "total_min": round(walk_min + wait + config.EAT_MINUTES_PER_STOP * len(stops)),
        }

    def attach_streets(self, stops: list[dict], centre: tuple[float, float]) -> dict:
        """Swap estimated legs for real walking routes where the router answers (display only)."""
        if not stops:
            return {"used": False, "legs": 0}
        estimated_m = sum(s["leg"]["walk_m"] for s in stops[1:])
        points = [centre] + [(s["stall"]["lat"], s["stall"]["lng"]) for s in stops]
        found = 0
        for stop, leg in zip(stops, streets.walking_legs(points)):
            if leg is None:
                continue
            found += 1
            stop["leg"].update({
                "walk_km": round(leg["distance_m"] / 1000, 3),
                "walk_m": int(round(leg["distance_m"])),
                "walk_min": round(leg["duration_min"], 1),
                "geometry": [[round(lat, 6), round(lng, 6)] for lat, lng in leg["coords"]],
                "source": "streets",
            })
        street_m = sum(s["leg"]["walk_m"] for s in stops[1:])
        return {"used": found > 0, "legs": found, "of": len(stops),
                "estimated_m": int(estimated_m), "street_m": int(street_m)}


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return Engine(get_dataset())


# ---------------------------------------------------------------- full request
def _fmt_time(hhmm: str) -> str:
    from .relax import _fmt_time as fmt
    return fmt(hhmm)


def _understood(p: Preferences, parsed: list[str], locked: list[str], ds: Dataset) -> list[dict]:
    """Plain-language list of what the request was read as, and where each value came from."""
    def src(*keys: str) -> str:
        if any(k in locked for k in keys):
            return "you"
        if any(k in parsed for k in keys):
            return "request"
        return "default"

    diet = {"veg": "Veg", "jain": "Jain", "non_veg": "Non-veg", "any": "Anything"}[p.diet]
    rows = [
        {"label": "Area", "value": p.area, "source": src("area")},
        {"label": "Diet", "value": diet, "source": src("diet")},
        {"label": "Spice", "value": (f"Around {p.spice_target}/5" if p.spice_target else "Any")
         + (f", max {p.spice_max}" if p.spice_max < 5 else ""), "source": src("spice_target", "spice_max")},
        {"label": "Budget", "value": f"₹{p.budget_total_inr} for {p.stops} stops" if p.budget_total_inr else "No limit",
         "source": src("budget_total_inr")},
        {"label": "Stops", "value": str(p.stops), "source": src("stops")},
        {"label": "When", "value": _fmt_time(p.time) if p.time else "Now", "source": src("time")},
        {"label": "Walk", "value": f"Up to {p.max_walk_km:g} km", "source": src("max_walk_km")},
    ]
    if p.include_categories:
        rows.append({"label": "Craving", "value": ", ".join(CATEGORY_LABELS.get(c, c) for c in p.include_categories),
                     "source": src("include_categories")})
    if p.exclude_categories:
        rows.append({"label": "Skipping", "value": ", ".join(CATEGORY_LABELS.get(c, c) for c in p.exclude_categories),
                     "source": src("exclude_categories")})
    if p.vibes:
        from ..data_loader import VIBE_LABELS
        rows.append({"label": "Mood", "value": ", ".join(VIBE_LABELS.get(v, v) for v in p.vibes),
                     "source": src("vibes")})
    if p.end_with_dessert:
        rows.append({"label": "Finish", "value": "Something sweet", "source": src("end_with_dessert")})
    return rows


def recommend(text: str | None, ui_prefs, profile_id: str | None = None,
              exclude_ids=(), pinned_ids=()) -> dict:
    from ..explain import explain
    from ..intent import understand
    from .relax import build_notice

    engine = get_engine()
    ds = engine.ds
    t0 = time.perf_counter()
    it = understand(text, ui_prefs, ds)
    p: Preferences = it["preferences"]
    t_intent = time.perf_counter() - t0

    profile = ds.users_by_id.get(profile_id) if profile_id else None
    plan = engine.plan(p, profile_id if profile else None, exclude_ids, pinned_ids)
    stops, _ = engine.assemble(plan)

    t_s = time.perf_counter()
    street_info = engine.attach_streets(stops, engine.centre(p.area))
    totals = engine.totals(stops)
    t_streets = time.perf_counter() - t_s

    t1 = time.perf_counter()
    lines, explain_source = explain(stops, p.spice_target, text or "")
    for s in stops:
        s["why"] = lines[s["stall"]["id"]]
    t_explain = time.perf_counter() - t1

    t2 = time.perf_counter()
    notice = build_notice(engine, p, len(stops), plan["filters"], len(plan["filtered"]),
                          it["requested_stops"], plan["ctx"].minutes, profile_id if profile else None,
                          exclude_ids, pinned_ids)
    t_notice = time.perf_counter() - t2

    timings = dict(plan["timings_ms"])
    timings.update({"intent": round(t_intent * 1000, 2), "streets": round(t_streets * 1000, 2),
                    "explain": round(t_explain * 1000, 2),
                    "notice": round(t_notice * 1000, 2), "total": round((time.perf_counter() - t0) * 1000, 2)})
    trace = {
        "parser_used": it["parser_used"],
        "llm_error": it["llm_error"],
        "explain_source": explain_source,
        "understood": _understood(p, it["parsed_fields"], it["locked_fields"], ds),
        "requested_stops": it["requested_stops"],
        "profile": {"id": profile.user_id, "name": profile.name} if profile else None,
        "filters": plan["filters"],
        "scoring": plan["scoring"],
        "diversity": plan["diversity"],
        "routing": {**plan["routing"], "streets": street_info},
        "alternatives": plan["alternatives"],
        "timings_ms": timings,
    }
    return {"preferences": p, "stops": stops, "totals": totals, "trace": trace, "notice": notice}
