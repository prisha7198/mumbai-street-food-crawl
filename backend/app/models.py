"""Pydantic v2 schemas for the data files and the API."""
from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import config

HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

VegType = Literal["veg", "non_veg", "both"]
Diet = Literal["veg", "non_veg", "any", "jain"]


def _check_hhmm(v: str) -> str:
    if not HHMM.match(v):
        raise ValueError(f"time must be HH:MM, got {v!r}")
    return v


# ---------------------------------------------------------------- data files
class Stall(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    type: str
    area: str
    landmark_hint: str = ""
    lat: float = Field(ge=18.85, le=19.35)   # Mumbai bounding box
    lng: float = Field(ge=72.75, le=73.05)
    category: str
    signature_dishes: list[str] = Field(min_length=1)
    veg_type: VegType
    jain_options: bool = False
    spice_level: int = Field(ge=1, le=5)
    price_per_person_inr: int = Field(gt=0)
    price_band: str = ""
    rating: float = Field(ge=0, le=5)
    review_count: int = Field(ge=0)
    open_time: str
    close_time: str
    closed_day: Optional[str] = None
    peak_hours: str = ""
    avg_wait_minutes: int = Field(ge=0, default=0)
    seating: str = ""
    hygiene_score: int = Field(ge=1, le=5, default=3)
    payment: list[str] = []
    vibe_tags: list[str] = []
    description: str = ""
    sample_reviews: list[str] = []

    _hhmm_open = field_validator("open_time", "close_time")(_check_hhmm)

    @field_validator("closed_day")
    @classmethod
    def _day(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, "", "none", "None"):
            return None
        v = v.strip().capitalize()
        if v not in DAYS:
            raise ValueError(f"closed_day must be a weekday, got {v!r}")
        return v

    @model_validator(mode="after")
    def _jain_needs_veg(self) -> "Stall":
        if self.jain_options and self.veg_type == "non_veg":
            raise ValueError("a non_veg stall cannot advertise jain options")
        return self


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    name: str
    home_area: str
    diet: Diet
    spice_tolerance: int = Field(ge=1, le=5)
    budget_per_person_inr: int = Field(gt=0)
    favourite_categories: list[str] = []


class Rating(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    stall_id: str
    rating: float = Field(ge=1, le=5)
    visited_on: Optional[str] = None


# ---------------------------------------------------------------- preferences
class Preferences(BaseModel):
    area: str = config.DEFAULT_AREA
    diet: Diet = "any"
    spice_target: Optional[int] = Field(default=None, ge=1, le=5)        # None = no preference
    spice_max: int = Field(default=5, ge=1, le=5)
    budget_total_inr: Optional[int] = Field(default=None, ge=20, le=20_000)  # None = no limit
    stops: int = Field(default=config.DEFAULT_STOPS, ge=config.MIN_STOPS, le=config.MAX_STOPS)
    include_categories: list[str] = []
    exclude_categories: list[str] = []
    vibes: list[str] = []
    end_with_dessert: bool = False
    time: Optional[str] = None          # HH:MM, None means "now" in Asia/Kolkata
    day: Optional[str] = None           # weekday, None means today
    max_walk_km: float = Field(default=config.DEFAULT_MAX_WALK_KM, gt=0, le=10)

    @field_validator("time")
    @classmethod
    def _time(cls, v: Optional[str]) -> Optional[str]:
        return None if v in (None, "") else _check_hhmm(v)

    @model_validator(mode="after")
    def _spice_order(self) -> "Preferences":
        if self.spice_target is not None and self.spice_target > self.spice_max:
            self.spice_target = self.spice_max
        return self


class PreferencesPatch(BaseModel):
    """Explicit UI controls. Anything set here wins over the parser.

    spice_target = 0 means "any spice" and budget_total_inr = 0 means "no limit",
    so the UI can lock those choices explicitly.
    """
    model_config = ConfigDict(extra="ignore")

    area: Optional[str] = None
    diet: Optional[Diet] = None
    spice_target: Optional[int] = Field(default=None, ge=0, le=5)
    spice_max: Optional[int] = Field(default=None, ge=1, le=5)
    budget_total_inr: Optional[int] = Field(default=None, ge=0, le=20_000)
    stops: Optional[int] = Field(default=None, ge=config.MIN_STOPS, le=config.MAX_STOPS)
    include_categories: Optional[list[str]] = None
    exclude_categories: Optional[list[str]] = None
    vibes: Optional[list[str]] = None
    end_with_dessert: Optional[bool] = None
    time: Optional[str] = None
    day: Optional[str] = None
    max_walk_km: Optional[float] = Field(default=None, gt=0, le=10)


# ---------------------------------------------------------------- API
class IntentRequest(BaseModel):
    text: str = ""
    preferences: Optional[PreferencesPatch] = None


class IntentResponse(BaseModel):
    preferences: Preferences
    parser_used: Literal["claude", "rules"]
    requested_stops: Optional[int] = None
    notes: list[str] = []


class RecommendRequest(BaseModel):
    text: Optional[str] = None
    preferences: Optional[PreferencesPatch] = None
    profile_id: Optional[str] = None
    exclude_ids: list[str] = []
    pinned_ids: list[str] = []


class RecommendResponse(BaseModel):
    preferences: Preferences
    stops: list[dict[str, Any]]
    totals: dict[str, Any]
    trace: dict[str, Any]
    notice: Optional[dict[str, Any]] = None
