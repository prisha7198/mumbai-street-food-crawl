"""Load and validate the data files once at startup.

Accepts either three files (stalls.json, users.json, ratings.json) or a
single combined JSON file with "stalls", "users" and "ratings" keys.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from . import config
from .models import Rating, Stall, User

CATEGORY_LABELS = {
    "vada_pav": "Vada pav",
    "pav_bhaji": "Pav bhaji",
    "chaat": "Chaat",
    "sandwich": "Sandwiches",
    "south_indian": "South Indian",
    "kebabs": "Kebabs and tikka",
    "frankie_rolls": "Frankies and rolls",
    "indo_chinese": "Indo-Chinese",
    "seafood": "Seafood",
    "misal": "Misal",
    "kulfi_desserts": "Kulfi and desserts",
    "juice_falooda": "Juice and falooda",
    "chai_snacks": "Chai and snacks",
    "biryani": "Biryani",
}
VIBE_LABELS = {
    "late_night": "Late night",
    "quick_bite": "Quick bite",
    "family_friendly": "Family friendly",
    "iconic": "Iconic",
    "hidden_gem": "Hidden gem",
    "beachside": "Beachside",
    "office_crowd": "Office crowd",
    "student_favourite": "Student favourite",
    "queue_worthy": "Worth the queue",
    "breakfast": "Breakfast",
    "sit_down": "Sit down",
    "crowded_lanes": "Busy lanes",
}


def label_for(key: str, labels: dict[str, str]) -> str:
    return labels.get(key, key.replace("_", " ").capitalize())


@dataclass
class Dataset:
    stalls: list[Stall]
    users: list[User]
    ratings: list[Rating]
    by_id: dict[str, Stall] = field(default_factory=dict)
    users_by_id: dict[str, User] = field(default_factory=dict)
    areas: dict[str, dict] = field(default_factory=dict)      # name -> {lat, lng, count}
    categories: list[str] = field(default_factory=list)
    vibes: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def index_of(self) -> dict[str, int]:
        return {s.id: i for i, s in enumerate(self.stalls)}


def _read_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _raw_records(data_dir: Path) -> tuple[list, list, list]:
    stalls_p, users_p, ratings_p = (data_dir / n for n in ("stalls.json", "users.json", "ratings.json"))
    if stalls_p.exists():
        stalls = _read_json(stalls_p)
        if isinstance(stalls, dict):            # stalls.json may itself be the combined file
            return stalls.get("stalls", []), stalls.get("users", []), stalls.get("ratings", [])
        users = _read_json(users_p) if users_p.exists() else []
        ratings = _read_json(ratings_p) if ratings_p.exists() else []
        return stalls, users, ratings
    for p in sorted(data_dir.glob("*.json")):     # any combined file
        blob = _read_json(p)
        if isinstance(blob, dict) and "stalls" in blob:
            return blob["stalls"], blob.get("users", []), blob.get("ratings", [])
    raise FileNotFoundError(f"No stalls.json or combined data file found in {data_dir}")


def _validate(rows: list, model, kind: str, skipped: list[str]) -> list:
    out = []
    for i, row in enumerate(rows):
        try:
            out.append(model.model_validate(row))
        except ValidationError as e:
            first = e.errors()[0]
            where = ".".join(str(x) for x in first["loc"]) or "row"
            ident = row.get("id") or row.get("user_id") or f"#{i}" if isinstance(row, dict) else f"#{i}"
            skipped.append(f"{kind} {ident}: {where} {first['msg']}")
    return out


def load_dataset(data_dir: Path | None = None, verbose: bool = True) -> Dataset:
    data_dir = Path(data_dir or config.DATA_DIR)
    raw_s, raw_u, raw_r = _raw_records(data_dir)
    skipped: list[str] = []

    stalls = _validate(raw_s, Stall, "stall", skipped)
    seen: set[str] = set()
    unique = []
    for s in stalls:
        if s.id in seen:
            skipped.append(f"stall {s.id}: duplicate id")
            continue
        seen.add(s.id)
        unique.append(s)
    stalls = unique

    users = _validate(raw_u, User, "user", skipped)
    ratings = _validate(raw_r, Rating, "rating", skipped)
    user_ids = {u.user_id for u in users}
    kept = []
    for r in ratings:
        if r.stall_id not in seen:
            skipped.append(f"rating {r.user_id}/{r.stall_id}: unknown stall")
        elif user_ids and r.user_id not in user_ids:
            skipped.append(f"rating {r.user_id}/{r.stall_id}: unknown user")
        else:
            kept.append(r)
    ratings = kept

    ds = Dataset(stalls=stalls, users=users, ratings=ratings, skipped=skipped)
    ds.by_id = {s.id: s for s in stalls}
    ds.users_by_id = {u.user_id: u for u in users}

    # area centre = mean of its stalls' coordinates
    for area in sorted({s.area for s in stalls}):
        pts = np.array([[s.lat, s.lng] for s in stalls if s.area == area])
        ds.areas[area] = {"lat": float(pts[:, 0].mean()), "lng": float(pts[:, 1].mean()), "count": len(pts)}

    ds.categories = sorted({s.category for s in stalls})
    ds.vibes = sorted({v for s in stalls for v in s.vibe_tags})

    if verbose:
        print_summary(ds)
    return ds


def print_summary(ds: Dataset) -> None:
    line = "-" * 56
    print(line)
    print(f"Loaded {len(ds.stalls)} stalls, {len(ds.users)} users, {len(ds.ratings)} ratings")
    print("Stalls per area:")
    for area, info in ds.areas.items():
        print(f"  {area:<22}{info['count']:>4}   centre {info['lat']:.4f}, {info['lng']:.4f}")
    print("Stalls per category:")
    for cat, n in sorted(Counter(s.category for s in ds.stalls).items(), key=lambda kv: -kv[1]):
        print(f"  {cat:<22}{n:>4}")
    if ds.skipped:
        print(f"Skipped {len(ds.skipped)} invalid rows:")
        for msg in ds.skipped[:20]:
            print(f"  {msg}")
        if len(ds.skipped) > 20:
            print(f"  ...and {len(ds.skipped) - 20} more")
    else:
        print("No invalid rows.")
    print(line)


@lru_cache(maxsize=1)
def get_dataset() -> Dataset:
    return load_dataset()
