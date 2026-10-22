"""Stage 2: hard constraints.

Rules run in a fixed order and each one records how many stalls it removed,
so the UI can show a funnel: 172 stalls -> 41 near Dadar -> 18 veg -> ...
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import config
from ..geo import walk_km
from ..hours import is_open, resolve_when, session_day
from ..models import Preferences, Stall


@dataclass
class FilterContext:
    centre: tuple[float, float]
    minutes: int
    day: str
    per_stop_cap: float | None
    exclude_ids: set[str] = field(default_factory=set)


def diet_ok(s: Stall, diet: str) -> bool:
    if diet == "jain":
        return s.jain_options                 # jain implies veg; non_veg stalls never have it
    if diet == "veg":
        return s.veg_type != "non_veg"        # "both" stalls still serve veg
    if diet == "non_veg":
        return s.veg_type != "veg"
    return True


def time_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def rules(p: Preferences, ctx: FilterContext):
    """(key, plain-language label, keep-predicate) in the order they are applied."""
    def distance(s: Stall) -> bool:
        return walk_km(ctx.centre[0], ctx.centre[1], s.lat, s.lng) / config.DETOUR_FACTOR <= p.max_walk_km

    diet_word = {"jain": "Not Jain friendly", "veg": "Serves only non-veg",
                 "non_veg": "Pure veg", "any": "Diet"}[p.diet]
    excluded = ", ".join(c.replace("_", " ") for c in p.exclude_categories)
    return [
        ("excluded", "Swapped out or removed", lambda s: s.id not in ctx.exclude_ids),
        ("distance", f"More than {p.max_walk_km:g} km from {p.area}", distance),
        ("diet", diet_word, lambda s: diet_ok(s, p.diet)),
        ("category", f"In a category you skipped ({excluded})" if excluded else "Skipped category",
         lambda s: s.category not in p.exclude_categories),
        ("spice", f"Spicier than {p.spice_max}/5", lambda s: s.spice_level <= p.spice_max),
        ("closed_day", "Weekly day off", lambda s: s.closed_day != session_day(s, ctx.minutes, ctx.day)),
        ("hours", f"Not open at {time_label(ctx.minutes)}", lambda s: is_open(s, ctx.minutes, ctx.day)),
        ("price", f"Over ₹{ctx.per_stop_cap:.0f} a stop" if ctx.per_stop_cap else "Over budget",
         lambda s: ctx.per_stop_cap is None or s.price_per_person_inr <= ctx.per_stop_cap),
    ]


def make_context(p: Preferences, centre: tuple[float, float], exclude_ids=None) -> FilterContext:
    minutes, day = resolve_when(p.time, p.day)
    cap = p.budget_total_inr / p.stops * config.PRICE_CAP_MULTIPLIER if p.budget_total_inr else None
    return FilterContext(centre=centre, minutes=minutes, day=day, per_stop_cap=cap,
                         exclude_ids=set(exclude_ids or []))


def apply_filters(stalls: list[Stall], p: Preferences, ctx: FilterContext) -> tuple[list[Stall], dict]:
    remaining = list(stalls)
    steps = []
    for key, label, keep in rules(p, ctx):
        before = len(remaining)
        remaining = [s for s in remaining if keep(s)]
        removed = before - len(remaining)
        if (key == "excluded" and not ctx.exclude_ids) or (key == "price" and ctx.per_stop_cap is None):
            continue
        steps.append({"rule": key, "label": label, "removed": removed, "remaining": len(remaining)})
    return remaining, {
        "start": len(stalls),
        "steps": steps,
        "remaining": len(remaining),
        "time": time_label(ctx.minutes),
        "day": ctx.day,
        "per_stop_cap": round(ctx.per_stop_cap) if ctx.per_stop_cap else None,
    }
