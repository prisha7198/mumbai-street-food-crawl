"""Stage 6: one short "why this stop" line per stop.

Lines are grounded only in the stall record and the route (dish, spice,
price, rating, walk from the previous stop). Claude writes all of them in a
single JSON call; any missing, too long or malformed line is replaced by the
template version, and the whole thing falls back to templates offline.
"""
from __future__ import annotations

from . import config, llm
from .data_loader import CATEGORY_LABELS

MAX_WORDS = 18
KEEP_CAPS = {"Mysore", "Kolhapuri", "Bombay", "Jain", "Irani", "Schezwan"}


def _dish(name: str) -> str:
    first = name.split()[0]
    return name if first in KEEP_CAPS else name[0].lower() + name[1:]


def _walk(minutes: float) -> str:
    m = max(1, round(minutes))
    return f"{m} min"


def template_line(f: dict) -> str:
    dish = _dish(f["dish"])
    price = f"₹{f['price']}"
    first = f["position"] == 1
    walk = f"{_walk(f['walk_min'])} from {'the start' if first else 'your last stop'}"
    if f["is_last"] and f["is_dessert"] and f["position"] > 1:
        line = f"A sweet finish with {dish}, {walk}, about {price}."
    elif f["spice"] >= 4 and (f["spice_target"] or 0) >= 4:
        line = f"Fiery {dish} at spice {f['spice']}/5. {walk.capitalize()}, about {price}."
    elif f["rating"] >= 4.5 and f["reviews"] >= 300:
        line = f"Known for {dish}, rated {f['rating']} by {f['reviews']:,} people. {_walk(f['walk_min'])} away, {price}."
    elif first:
        line = f"Start with their {dish}. {walk.capitalize()}, around {price}."
    else:
        line = f"Known for {dish}. {walk.capitalize()}, around {price}."
    if len(line.split()) > MAX_WORDS:
        line = f"Known for {dish}. {_walk(f['walk_min'])} walk, around {price}."
    return line


def facts_for(stops: list[dict], spice_target: int) -> list[dict]:
    out = []
    for i, s in enumerate(stops):
        st = s["stall"]
        out.append({
            "stall_id": st["id"],
            "position": i + 1,
            "name": st["name"],
            "dish": st["signature_dishes"][0],
            "other_dishes": st["signature_dishes"][1:],
            "category": CATEGORY_LABELS.get(st["category"], st["category"]),
            "spice": st["spice_level"],
            "spice_target": spice_target,
            "price": st["price_per_person_inr"],
            "rating": st["rating"],
            "reviews": st["review_count"],
            "walk_min": round(s["leg"]["walk_min"], 1),
            "walk_from": "the start" if i == 0 else "the previous stop",
            "wait_min": st["avg_wait_minutes"],
            "is_last": i == len(stops) - 1,
            "is_dessert": st["category"] in config.DESSERT_CATEGORIES,
        })
    return out


SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"stall_id": {"type": "string"}, "why": {"type": "string"}},
                "required": ["stall_id", "why"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["lines"],
    "additionalProperties": False,
}

SYSTEM = (
    "You write one line per stop for a Mumbai street food crawl, explaining why the stop was chosen. "
    f"Each line is at most {MAX_WORDS} words, sentence case, no emoji, no exclamation marks. "
    "Use only facts given in the JSON: dish names, spice level, price in rupees, rating, review count, "
    "walking minutes from the previous stop (or from the start for stop 1). Never invent a fact, award, "
    "ingredient, owner, history or opening time. Write the rupee symbol as ₹. Vary the wording between lines."
)


def explain(stops: list[dict], spice_target: int, request_text: str = "") -> tuple[dict[str, str], str]:
    """Return ({stall_id: line}, source) where source is 'claude' or 'template'."""
    facts = facts_for(stops, spice_target)
    lines = {f["stall_id"]: template_line(f) for f in facts}
    if not facts or not llm.available():
        return lines, "template"
    import json
    user = json.dumps({"request": request_text, "stops": facts}, ensure_ascii=False)
    result = llm.call_json(SYSTEM, user, SCHEMA, timeout=config.EXPLAIN_TIMEOUT_S)
    if not result:
        return lines, "template"
    used = 0
    for item in result.get("lines", []):
        sid, why = item.get("stall_id"), (item.get("why") or "").strip()
        if sid in lines and why and len(why.split()) <= MAX_WORDS:
            lines[sid] = why
            used += 1
    return lines, "claude" if used == len(facts) else ("mixed" if used else "template")
