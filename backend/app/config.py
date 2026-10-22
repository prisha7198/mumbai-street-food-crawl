"""Every tunable number in one place, so the viva answer to "where is X set?" is always this file."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent

# .env in the repo root or in /backend, whichever exists
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
TIMEZONE = "Asia/Kolkata"

# ---------------------------------------------------------------- Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5").strip() or "claude-haiku-5-5"
INTENT_TIMEOUT_S = 4.0
EXPLAIN_TIMEOUT_S = 6.0
# Set USE_CLAUDE=0 to force the offline path even when a key is present.
USE_CLAUDE = os.getenv("USE_CLAUDE", "1") != "0"

# ---------------------------------------------------------------- defaults
DEFAULT_STOPS = 4
MIN_STOPS, MAX_STOPS = 2, 6
DEFAULT_BUDGET_TOTAL = None         # no limit unless asked
BUDGET_STEP = 50                    # ₹ step of the UI budget stepper
BUDGET_FIRST_STEP = 400             # first value when stepping up from "no limit"
DEFAULT_MAX_WALK_KM = 2.5
DEFAULT_AREA = "Dadar"

# ---------------------------------------------------------------- filters
PRICE_CAP_MULTIPLIER = 1.5          # a stop may cost up to 1.5x its share of the budget

# ---------------------------------------------------------------- features
# Block weights for the stall / intent vectors (applied before cosine).
FEATURE_WEIGHTS = {
    "category": 1.0,
    "vibe": 0.6,
    "spice": 0.8,
    "price": 0.6,
    "diet": 0.5,
}
SPICE_SIGMA = 0.8                   # width of the soft spice encoding (in spice levels)
PRICE_BINS = [0, 50, 100, 150, 250, 400, 10_000]  # ₹ per person, bin edges
PRICE_SIGMA = 0.9                   # width of the soft price encoding (in bins)

# ---------------------------------------------------------------- scoring
HYBRID_WEIGHTS = {"content": 0.45, "quality": 0.30, "cf": 0.25}
BAYES_PERCENTILE = 60               # m = 60th percentile of review counts
CF_K = 10                           # neighbours used for item-based CF
WAIT_PENALTY = 0.06                 # max penalty for a long queue
WAIT_PENALTY_FROM = 10              # minutes; no penalty below this
WAIT_PENALTY_FULL = 25              # minutes; full penalty at or above this
HYGIENE_PENALTY = 0.08              # max penalty, applied below hygiene 3
HYGIENE_OK = 3

# ---------------------------------------------------------------- diversity
MMR_LAMBDA = 0.7
MMR_POOL = 30                       # re-rank the top 30 by hybrid score

# ---------------------------------------------------------------- routing
DETOUR_FACTOR = 1.3                 # straight-line km -> street km
WALK_SPEED_KMH = 4.5
ROUTE_ALPHA = 0.25                  # score units given up per extra km walked
ROUTE_POOL = 25                     # candidates the route builder considers
EAT_MINUTES_PER_STOP = 10           # used only for the total time estimate
DESSERT_CATEGORIES = ("kulfi_desserts", "juice_falooda")

# ---------------------------------------------------------------- street routing (display only)
# Walking paths for the map come from the FOSSGIS OSRM foot router (OpenStreetMap data, no key).
# Set USE_STREET_ROUTING=0 to keep straight lines, e.g. for a fully offline demo.
USE_STREET_ROUTING = os.getenv("USE_STREET_ROUTING", "1") != "0"
STREET_ROUTING_URL = os.getenv("STREET_ROUTING_URL", "https://routing.openstreetmap.de/routed-foot/route/v1/foot")
STREET_ROUTING_USER_AGENT = "mumbai-street-food-crawl/1.0 (college project demo)"
STREET_ROUTING_TIMEOUT_S = 4.0
STREET_ROUTING_COOLDOWN_S = 60     # after a failure, stop asking for this long

# ---------------------------------------------------------------- relaxation
RELAX_BUDGET_FACTORS = (1.25, 1.5, 2.0, 3.0)
RELAX_BUDGET_PER_STOP = (100, 150, 250)     # also try these absolute ₹ per stop
RELAX_WALK_KM = (3.5, 5.0)
RELAX_TIMES = ("08:30", "13:00", "17:00", "19:30", "21:30", "23:30")
