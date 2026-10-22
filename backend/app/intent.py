"""Stage 1: turn free text into Preferences.

Primary path: Claude reads the sentence and calls a `set_preferences` tool
whose JSON schema lists the only valid areas, categories and vibes.
Fallback path: a rule-based parser (regular expressions + synonym maps).
Either way, explicit UI controls are applied last and always win.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import config, llm
from .data_loader import CATEGORY_LABELS, VIBE_LABELS, Dataset
from .hours import now_local
from .models import DAYS, Preferences, PreferencesPatch

# ---------------------------------------------------------------- synonym maps
AREA_ALIASES = {
    "Dadar": [r"dadar", r"shivaji park", r"kabutar ?khana"],
    "Mohammed Ali Road": [r"mohammed ali", r"mohammad ali", r"mohd\.? ali", r"muhammad ali", r"minara",
                          r"bohri mohalla", r"bhendi bazaa?r", r"\bmar\b"],
    "Ghatkopar": [r"ghatkopar"],
    "Juhu": [r"juhu"],
    "Colaba": [r"colaba", r"causeway"],
    "Bandra": [r"bandra", r"carter road", r"hill road", r"linking road"],
    "Girgaum Chowpatty": [r"chowpatty", r"girgaum", r"girgaon", r"marine drive"],
    "Matunga": [r"matunga", r"king'?s circle"],
    "Vile Parle": [r"vile ?parle", r"\bparle\b"],
    "Fort": [r"\bfort\b", r"kala ghoda", r"\bcst\b", r"\bcsmt\b", r"\bvt\b", r"flora fountain"],
}

CATEGORY_SYNONYMS = {
    "vada_pav": [r"vada ?pav", r"wada ?pav", r"vadapav", r"chura pav", r"bhajji pav"],
    "pav_bhaji": [r"pav ?bhaji", r"bhaji pav", r"tawa pulao"],
    "chaat": [r"chaat", r"chat\b", r"pani ?puri", r"golgappa", r"gol gappa", r"bhel", r"sev ?puri",
              r"dahi ?puri", r"ragda", r"pattice"],
    "sandwich": [r"sandwich", r"toast", r"bombay masala"],
    "south_indian": [r"dosa", r"idli", r"south indian", r"medu vada", r"uttapa?m", r"filter coffee", r"udupi"],
    "kebabs": [r"kebabs?", r"kababs?", r"tikka", r"seekh", r"tandoori", r"grill", r"bbq", r"barbecue",
               r"bheja", r"nihari", r"baida roti"],
    "frankie_rolls": [r"frankie", r"\brolls?\b", r"wraps?", r"kathi"],
    "indo_chinese": [r"chinese", r"manchurian", r"schezwan", r"szechuan", r"noodles", r"fried rice",
                     r"momos?", r"hakka"],
    "seafood": [r"seafood", r"sea food", r"\bfish\b", r"prawns?", r"bombil", r"surmai", r"crabs?",
                r"koliwada", r"pomfret"],
    "misal": [r"misal", r"usal", r"poha", r"sabudana"],
    "kulfi_desserts": [r"kulfi", r"ice ?cream", r"malpua", r"phirni", r"jalebi", r"rabdi", r"rabri",
                       r"mithai", r"desserts?", r"\bsweets?\b", r"meetha", r"mithas?"],
    "juice_falooda": [r"juice", r"falooda", r"faluda", r"sugarcane", r"milkshake", r"shake\b", r"lassi",
                      r"\bgola\b", r"something cold"],
    "chai_snacks": [r"\bchai\b", r"cutting", r"\btea\b", r"bun maska", r"coffee", r"irani", r"samosa"],
    "biryani": [r"biryani", r"biriyani", r"pulao", r"kheema", r"keema"],
}
SWEET_WORDS = r"(sweet|dessert|meetha|mithai|kulfi|falooda|ice ?cream|something cold)"
END_WITH_SWEET = [
    SWEET_WORDS + r"\s+(at|in|for)\s+the\s+(end|last)",
    r"end(ing)?\s+(it\s+)?(with|on)\s+(something\s+)?" + SWEET_WORDS,
    r"finish(ing)?\s+(it\s+)?(with|on)\s+(something\s+)?" + SWEET_WORDS,
    r"(to\s+finish|to\s+end|round\s+(it\s+)?off)\s+(with\s+)?(something\s+)?" + SWEET_WORDS,
    r"(last|final)\s+stop\s+.*" + SWEET_WORDS,
    r"then\s+(something\s+)?" + SWEET_WORDS,
]
VIBE_SYNONYMS = {
    "late_night": [r"late ?night", r"midnight", r"after hours", r"night owl", r"\b(1|2|3|4) ?am\b"],
    "quick_bite": [r"quick", r"on the go", r"in a hurry", r"fast\b"],
    "family_friendly": [r"family", r"kids", r"parents", r"children"],
    "iconic": [r"iconic", r"famous", r"legendary", r"must[ -]try", r"classic", r"popular"],
    "hidden_gem": [r"hidden", r"underrated", r"lesser[- ]known", r"offbeat", r"secret"],
    "beachside": [r"beach", r"seaside", r"by the sea", r"sea face"],
    "office_crowd": [r"office", r"after work", r"work crowd"],
    "student_favourite": [r"student", r"college"],
    "queue_worthy": [r"worth the (queue|wait|line)"],
    "breakfast": [r"breakfast", r"morning", r"nashta"],
    "sit_down": [r"sit[- ]down", r"seating", r"place to sit", r"\bseated\b"],
    "crowded_lanes": [r"khau ?galli", r"food street", r"busy lanes?"],
}
NON_VEG_WORDS = r"\b(chicken|mutton|kebabs?|kababs?|tikka|seekh|fish|prawns?|seafood|biryani|eggs?|meat|bheja|nihari|keema|kheema|bombil|surmai|crab|tandoori)\b"
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "couple": 2, "few": 3}


@dataclass
class ParseResult:
    fields: dict = field(default_factory=dict)
    requested_stops: int | None = None
    notes: list[str] = field(default_factory=list)


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def _categories_in(text: str) -> list[str]:
    found = []
    for cat, pats in CATEGORY_SYNONYMS.items():
        if any(_has(p, text) for p in pats):
            found.append(cat)
    return found


def parse_rules(text: str, ds: Dataset | None = None) -> ParseResult:
    """Keyword parser. Only fills fields it actually found in the text."""
    t = " " + text.lower().replace("’", "'") + " "
    t = re.sub(r"\s+", " ", t)
    out = ParseResult()
    f = out.fields
    valid_areas = set(ds.areas) if ds else set(AREA_ALIASES)

    # ---- area
    for area, pats in AREA_ALIASES.items():
        if area in valid_areas and any(_has(p, t) for p in pats):
            f["area"] = area
            break

    # ---- stops
    m = re.search(r"\b(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")\s+(?:[a-z'-]+\s+){0,3}?"
                  r"(stops?|places?|stalls?|spots?|joints?|plates?|dishes|items|halts?)\b", t)
    if m:
        raw = m.group(1)
        n = int(raw) if raw.isdigit() else NUMBER_WORDS[raw]
        out.requested_stops = n
        f["stops"] = max(config.MIN_STOPS, min(config.MAX_STOPS, n))

    # ---- diet (non-veg checked before veg because "non veg" contains "veg")
    if _has(r"\bjain\b", t):
        f["diet"] = "jain"
    elif _has(r"\bnon[ -]?veg|\bnonveg|\bnon[ -]vegetarian", t):
        f["diet"] = "non_veg"
    elif _has(r"\b(pure veg|shudh veg|shuddh|vegetarian|veggie|no meat|\bveg\b)", t):
        f["diet"] = "veg"
    elif _has(NON_VEG_WORDS, t):
        f["diet"] = "non_veg"

    # ---- spice (mild phrases first because "not spicy" contains "spicy")
    if _has(r"\b(no spice|zero spice|not spicy at all|no teekha)\b", t):
        f["spice_target"], f["spice_max"] = 1, 2
    elif _has(r"\b(not (too |very |that )?spicy|mild|less spicy|kam (teekha|tikha)|light on spice|not hot)\b", t):
        f["spice_target"], f["spice_max"] = 2, 3
    elif _has(r"\b(extra|very|super|really|bahut|ekdum) (spicy|teekha|tikha|hot)\b|\bfiery\b|\bfire\b", t):
        f["spice_target"] = 5
    elif _has(r"\b(spicy|spice|teekha|tikha|teekhi|tikhi|chatpata|chatpati|masaledar|hot)\b", t):
        f["spice_target"] = 4

    # ---- budget
    amount = None
    for pat in (
        r"(?:under|below|within|less than|upto|up to|max(?:imum)?|budget(?: of| is)?|around|about|for)\s*(?:₹|rs\.?|inr|rupees)?\s*(\d{2,5})(?!\s*(?:am|pm|km|min|stops?))",
        r"(?:₹|rs\.?\s?|inr\s?)(\d{2,5})",
        r"\b(\d{2,5})\s*(?:rs\b|rupees|₹|inr\b|bucks)",
    ):
        m = re.search(pat, t)
        if m:
            amount = int(m.group(1))
            break
    if amount is not None:
        stops = f.get("stops", config.DEFAULT_STOPS)
        if _has(r"(per|a|each)\s+(stop|place|stall|spot|plate)", t):
            amount *= stops
            out.notes.append("Budget was per stop, multiplied by the number of stops")
        f["budget_total_inr"] = amount
    elif _has(r"\b(cheap|budget|affordable|pocket[- ]friendly|sasta|inexpensive|low cost)\b", t):
        f["budget_total_inr"] = 300
    elif _has(r"\b(splurge|fancy|no budget|money no bar)\b", t):
        f["budget_total_inr"] = 2000

    # ---- time
    m = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b", t)
    if m:
        h, mins, ap = int(m.group(1)) % 12, int(m.group(2) or 0), m.group(3)
        h += 12 if ap == "pm" else 0
        f["time"] = f"{h:02d}:{mins:02d}"
    elif _has(r"after midnight", t):
        f["time"] = "00:30"
    elif _has(r"\bmidnight\b", t):
        f["time"] = "00:00"
    elif _has(r"late ?night|after hours", t):
        f["time"] = "23:30"
    elif _has(r"\b(breakfast|morning|nashta)\b", t):
        f["time"] = "08:30"
    elif _has(r"\b(lunch|afternoon)\b", t):
        f["time"] = "13:00"
    elif _has(r"\b(evening|after work|sunset)\b", t):
        f["time"] = "19:00"
    elif _has(r"\b(tonight|dinner)\b", t):
        f["time"] = "20:30"
    for day in DAYS:
        if _has(r"\b" + day.lower() + r"\b", t):
            f["day"] = day

    # ---- categories, with negation ("no chinese", "skip seafood")
    excluded = []
    for m in re.finditer(r"\b(no|not|without|skip|avoid|except|minus|apart from)\s+((?:[a-z'-]+\s*){1,3})", t):
        excluded += _categories_in(" " + m.group(2) + " ")
        t = t.replace(m.group(0), " ")
    include = [c for c in _categories_in(t) if c not in excluded]

    # ---- something sweet at the end
    if any(_has(p, t) for p in END_WITH_SWEET):
        f["end_with_dessert"] = True
        include = [c for c in include if c not in config.DESSERT_CATEGORIES]
    elif "kulfi_desserts" in include and "juice_falooda" not in include and _has(r"\b(sweet|dessert|meetha)", t):
        include.append("juice_falooda")
    if include:
        f["include_categories"] = include
    if excluded:
        f["exclude_categories"] = sorted(set(excluded))

    # ---- vibes
    vibes = [v for v, pats in VIBE_SYNONYMS.items() if any(_has(p, t) for p in pats)]
    if ds:
        vibes = [v for v in vibes if v in ds.vibes]
    if vibes:
        f["vibes"] = vibes

    # ---- walking
    m = re.search(r"(?:within|under|max(?:imum)?|less than)\s*(\d+(?:\.\d+)?)\s*km", t)
    if m:
        f["max_walk_km"] = float(m.group(1))
    elif _has(r"short walk|less walking|not much walking|minimal walking|lazy|nearby|close by", t):
        f["max_walk_km"] = 1.5
    elif _has(r"don'?t mind walking|long walk|happy to walk", t):
        f["max_walk_km"] = 4.0
    return out


# ---------------------------------------------------------------- Claude path
def _tool_schema(ds: Dataset) -> dict:
    def nullable(schema: dict) -> dict:
        return {"anyOf": [schema, {"type": "null"}]}
    return {
        "name": "set_preferences",
        "description": "Record the street food crawl preferences expressed in the user's request. "
                       "Use null for anything the user did not mention.",
        "input_schema": {
            "type": "object",
            "properties": {
                "area": nullable({"type": "string", "enum": list(ds.areas)}),
                "diet": nullable({"type": "string", "enum": ["veg", "non_veg", "any", "jain"]}),
                "spice_target": nullable({"type": "integer", "description": "1 (no spice) to 5 (fiery)"}),
                "spice_max": nullable({"type": "integer", "description": "1-5, only if the user wants to cap spice"}),
                "budget_total_inr": nullable({"type": "integer", "description": "Total rupees per person for the whole crawl"}),
                "stops": nullable({"type": "integer", "description": "Number of stops exactly as asked, even if more than 6"}),
                "include_categories": {"type": "array", "items": {"type": "string", "enum": ds.categories}},
                "exclude_categories": {"type": "array", "items": {"type": "string", "enum": ds.categories}},
                "vibes": {"type": "array", "items": {"type": "string", "enum": ds.vibes}},
                "end_with_dessert": {"type": "boolean"},
                "time": nullable({"type": "string", "description": "24h HH:MM if the user mentioned a time or a meal"}),
                "max_walk_km": nullable({"type": "number"}),
            },
            "required": ["area", "diet", "spice_target", "spice_max", "budget_total_inr", "stops",
                         "include_categories", "exclude_categories", "vibes", "end_with_dessert", "time",
                         "max_walk_km"],
            "additionalProperties": False,
        },
    }


def _system_prompt(ds: Dataset) -> str:
    cats = "\n".join(f"- {c}: {CATEGORY_LABELS.get(c, c)}" for c in ds.categories)
    vibes = "\n".join(f"- {v}: {VIBE_LABELS.get(v, v)}" for v in ds.vibes)
    return (
        "You read requests for a Mumbai street food crawl and record them with the set_preferences tool. "
        "Always respond by calling set_preferences exactly once.\n\n"
        f"Valid areas: {', '.join(ds.areas)}.\n"
        f"Valid categories:\n{cats}\n"
        f"Valid vibes:\n{vibes}\n\n"
        "Rules:\n"
        "- Use null for anything not mentioned. Do not guess an area if none is named.\n"
        "- Hindi or Marathi words are common: teekha means spicy, shudh veg means pure veg, meetha means sweet.\n"
        "- A rupee amount like 'under 400' is the total budget per person unless they say per stop.\n"
        "- 'something sweet at the end' sets end_with_dessert true and does not add dessert categories.\n"
        "- Meat words such as kebab, chicken or fish imply diet non_veg unless the user says veg.\n"
        "- Late night means 23:30 unless a time is given. Breakfast means 08:30.\n"
        "- spice_target: spicy is 4, very spicy is 5, mild is 2. Set spice_max only for mild or no-spice requests."
    )


def parse_claude(text: str, ds: Dataset) -> ParseResult | None:
    if not text.strip() or not llm.available():
        return None
    now = now_local()
    user = f"Current time in Mumbai: {now:%A %H:%M}.\nRequest: {text.strip()}"
    raw = llm.call_tool(_system_prompt(ds), user, _tool_schema(ds), timeout=config.INTENT_TIMEOUT_S)
    if raw is None:
        return None
    out = ParseResult()
    f = out.fields
    if raw.get("area") in ds.areas:
        f["area"] = raw["area"]
    if raw.get("diet") in ("veg", "non_veg", "any", "jain"):
        f["diet"] = raw["diet"]
    for k in ("spice_target", "spice_max"):
        if isinstance(raw.get(k), int):
            f[k] = max(1, min(5, raw[k]))
    if isinstance(raw.get("budget_total_inr"), int) and raw["budget_total_inr"] > 0:
        f["budget_total_inr"] = max(20, min(20_000, raw["budget_total_inr"]))
    if isinstance(raw.get("stops"), int) and raw["stops"] > 0:
        out.requested_stops = raw["stops"]
        f["stops"] = max(config.MIN_STOPS, min(config.MAX_STOPS, raw["stops"]))
    for k, valid in (("include_categories", ds.categories), ("exclude_categories", ds.categories),
                     ("vibes", ds.vibes)):
        vals = [v for v in raw.get(k) or [] if v in valid]
        if vals:
            f[k] = vals
    if raw.get("end_with_dessert"):
        f["end_with_dessert"] = True
    if isinstance(raw.get("time"), str) and re.match(r"^([01]\d|2[0-3]):[0-5]\d$", raw["time"]):
        f["time"] = raw["time"]
    if isinstance(raw.get("max_walk_km"), (int, float)) and 0 < raw["max_walk_km"] <= 10:
        f["max_walk_km"] = float(raw["max_walk_km"])
    return out


# ---------------------------------------------------------------- public API
def understand(text: str | None, ui: PreferencesPatch | None, ds: Dataset) -> dict:
    """Return {preferences, parser_used, requested_stops, notes, parsed_fields, locked_fields}."""
    text = text or ""
    parsed = parse_claude(text, ds)
    parser_used = "claude"
    if parsed is None:
        parsed = parse_rules(text, ds)
        parser_used = "rules"

    merged = Preferences().model_dump()
    merged.update(parsed.fields)
    locked = {}
    if ui is not None:
        locked = {k: v for k, v in ui.model_dump(exclude_none=True).items()}
        merged.update(locked)
    if merged.get("spice_target") == 0:
        merged["spice_target"] = None
    if merged.get("budget_total_inr") == 0:
        merged["budget_total_inr"] = None
    if merged.get("area") not in ds.areas:
        merged["area"] = config.DEFAULT_AREA if config.DEFAULT_AREA in ds.areas else next(iter(ds.areas))
    # a spice target above the cap is lowered to the cap (UI may have changed only one)
    if merged["spice_target"] is not None and merged["spice_target"] > merged["spice_max"]:
        if "spice_target" in locked and "spice_max" not in locked:
            merged["spice_max"] = merged["spice_target"]
        else:
            merged["spice_target"] = merged["spice_max"]
    prefs = Preferences.model_validate(merged)

    requested = parsed.requested_stops if "stops" not in locked else None
    return {
        "preferences": prefs,
        "parser_used": parser_used,
        "requested_stops": requested,
        "notes": parsed.notes,
        "parsed_fields": sorted(parsed.fields),
        "locked_fields": sorted(locked),
        "llm_error": llm.last_error if parser_used == "rules" and llm.available() else None,
    }
