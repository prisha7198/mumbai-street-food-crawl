"""FastAPI app: routes only. All logic lives in intent.py, recommender/ and explain.py."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections import Counter

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import config, llm
from .data_loader import CATEGORY_LABELS, VIBE_LABELS, get_dataset, label_for
from .hours import resolve_when
from .intent import understand
from .models import IntentRequest, IntentResponse, RecommendRequest, RecommendResponse
from .recommender.pipeline import get_engine, recommend

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_engine()            # loads + validates data and prints the summary
    mode = f"Claude ({config.ANTHROPIC_MODEL})" if llm.available() else "offline (rule parser + templates)"
    print(f"Language layer: {mode}")
    print(f"Collaborative filtering: {len(engine.cf.user_ids)} users x {len(engine.cf.stall_ids)} stalls")
    yield


app = FastAPI(title="Mumbai street food crawl", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


def _demo_profiles() -> list[dict]:
    """Six varied profiles for the "Plan as" menu: one per diet first, then the most active raters."""
    ds = get_dataset()
    counts = Counter(r.user_id for r in ds.ratings)
    ranked = sorted(ds.users, key=lambda u: -counts[u.user_id])
    picked = []
    for diet in ("veg", "non_veg", "jain", "any", "veg", "non_veg"):
        for u in ranked:
            if u.diet == diet and u not in picked:
                picked.append(u)
                break
    diet_word = {"veg": "Veg", "non_veg": "Non-veg", "jain": "Jain", "any": "Eats anything"}
    out = []
    for u in picked:
        favs = [label_for(c, CATEGORY_LABELS).lower() for c in u.favourite_categories[:2]]
        out.append({
            "id": u.user_id,
            "name": u.name,
            "summary": f"{diet_word[u.diet]}, likes {' and '.join(favs)}",
            "home_area": u.home_area,
            "ratings": counts[u.user_id],
        })
    return out


@app.get("/api/health")
def health():
    ds = get_dataset()
    return {"status": "ok", "stalls": len(ds.stalls), "claude": llm.available(), "model": config.ANTHROPIC_MODEL}


@app.get("/api/meta")
def meta():
    ds = get_dataset()
    return {
        "areas": [{"name": a, **info} for a, info in ds.areas.items()],
        "categories": [{"id": c, "label": label_for(c, CATEGORY_LABELS)} for c in ds.categories],
        "vibes": [{"id": v, "label": label_for(v, VIBE_LABELS)} for v in ds.vibes],
        "profiles": _demo_profiles(),
        "defaults": {"area": config.DEFAULT_AREA, "stops": config.DEFAULT_STOPS,
                     "budget_total_inr": config.DEFAULT_BUDGET_TOTAL, "budget_step": config.BUDGET_STEP,
                     "budget_first_step": config.BUDGET_FIRST_STEP, "max_walk_km": config.DEFAULT_MAX_WALK_KM, "min_stops": config.MIN_STOPS,
                     "max_stops": config.MAX_STOPS},
        "claude": llm.available(),
    }


@app.get("/api/stalls")
def stalls(area: str | None = Query(default=None), category: str | None = Query(default=None)):
    engine = get_engine()
    minutes, day = resolve_when(None, None)
    out = []
    for s in engine.ds.stalls:
        if (area and s.area != area) or (category and s.category != category):
            continue
        d = engine.stall_out(s.id, minutes, day)
        d.pop("sample_reviews", None)
        out.append(d)
    return {"count": len(out), "stalls": out}


@app.get("/api/stalls/{stall_id}")
def stall(stall_id: str, time: str | None = None, day: str | None = None):
    engine = get_engine()
    if stall_id not in engine.ds.by_id:
        raise HTTPException(status_code=404, detail="Stall not found")
    minutes, wd = resolve_when(time, day)
    d = engine.stall_out(stall_id, minutes, wd)
    i = engine.idx[stall_id]
    d["bayesian_rating"] = round(float(engine.quality_raw[i]), 2)
    return d


@app.post("/api/intent", response_model=IntentResponse)
def intent(req: IntentRequest):
    it = understand(req.text, req.preferences, get_dataset())
    return IntentResponse(preferences=it["preferences"], parser_used=it["parser_used"],
                          requested_stops=it["requested_stops"], notes=it["notes"])


@app.post("/api/recommend", response_model=RecommendResponse)
def recommend_route(req: RecommendRequest):
    result = recommend(req.text, req.preferences, req.profile_id, req.exclude_ids, req.pinned_ids)
    return RecommendResponse(**result)
