import os
import sys
from pathlib import Path

# Tests always run offline so they are deterministic and free.
os.environ["USE_CLAUDE"] = "0"
os.environ["USE_STREET_ROUTING"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app.models import Stall  # noqa: E402


def make_stall(**kw) -> Stall:
    base = dict(
        id="t1", name="Test Stall", type="cart", area="Dadar", landmark_hint="", lat=19.02, lng=72.84,
        category="vada_pav", signature_dishes=["Vada pav"], veg_type="veg", jain_options=False, spice_level=3,
        price_per_person_inr=40, price_band="₹", rating=4.2, review_count=100, open_time="10:00",
        close_time="22:00", closed_day=None, peak_hours="19:00-21:00", avg_wait_minutes=5, seating="standing",
        hygiene_score=4, payment=["cash"], vibe_tags=[], description="", sample_reviews=[],
    )
    base.update(kw)
    return Stall.model_validate(base)


@pytest.fixture
def stall_factory():
    return make_stall
