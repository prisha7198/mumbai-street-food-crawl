import pytest

from app.data_loader import get_dataset
from app.intent import parse_rules, understand
from app.models import PreferencesPatch

# (sentence, expected subset of parsed fields)
CASES = [
    ("4 spicy veg stops near Dadar under ₹400, something sweet at the end",
     {"stops": 4, "diet": "veg", "area": "Dadar", "budget_total_inr": 400, "spice_target": 4,
      "end_with_dessert": True}),
    ("late night kebabs on Mohammed Ali Road",
     {"area": "Mohammed Ali Road", "diet": "non_veg", "time": "23:30", "include_categories": ["kebabs"]}),
    ("something cheap and sweet near Juhu beach",
     {"area": "Juhu", "budget_total_inr": 300}),
    ("jain friendly chaat in Ghatkopar",
     {"diet": "jain", "area": "Ghatkopar", "include_categories": ["chaat"]}),
    ("10 stops in Colaba at 3 AM under ₹50",
     {"stops": 6, "area": "Colaba", "time": "03:00", "budget_total_inr": 50}),
    ("teekha vada pav in Dadar, 3 stops, 200 rs",
     {"spice_target": 4, "include_categories": ["vada_pav"], "stops": 3, "budget_total_inr": 200}),
    ("shudh veg breakfast in Matunga, not too spicy",
     {"diet": "veg", "area": "Matunga", "time": "08:30", "spice_target": 2, "spice_max": 3}),
    ("non veg seafood in Bandra, no chinese",
     {"diet": "non_veg", "area": "Bandra", "include_categories": ["seafood"], "exclude_categories": ["indo_chinese"]}),
    ("five stops at kala ghoda for ₹100 per stop",
     {"stops": 5, "area": "Fort", "budget_total_inr": 500}),
    ("pav bhaji and kulfi at chowpatty within 1.5 km",
     {"area": "Girgaum Chowpatty", "max_walk_km": 1.5}),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_fallback_parser(text, expected):
    fields = parse_rules(text, get_dataset()).fields
    for key, value in expected.items():
        if key.endswith("categories"):
            assert set(value) <= set(fields.get(key, [])), (key, fields)
        else:
            assert fields.get(key) == value, (key, fields)


def test_requested_stops_recorded_before_clamp():
    out = parse_rules("10 stops in Colaba", get_dataset())
    assert out.requested_stops == 10 and out.fields["stops"] == 6


def test_chowpatty_includes_both_categories():
    fields = parse_rules("pav bhaji and kulfi at chowpatty", get_dataset()).fields
    assert {"pav_bhaji", "kulfi_desserts"} <= set(fields["include_categories"])


def test_ui_controls_override_parser():
    ds = get_dataset()
    it = understand("4 spicy veg stops near Dadar under ₹400", PreferencesPatch(area="Juhu", stops=3, diet="jain"), ds)
    p = it["preferences"]
    assert (p.area, p.stops, p.diet) == ("Juhu", 3, "jain")
    assert p.budget_total_inr == 400            # not overridden, so the parsed value stays
    assert it["parser_used"] == "rules"


def test_zero_means_any():
    ds = get_dataset()
    p = understand("spicy under 400 in Dadar", PreferencesPatch(spice_target=0, budget_total_inr=0), ds)["preferences"]
    assert p.spice_target is None and p.budget_total_inr is None
