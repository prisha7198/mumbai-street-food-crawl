"""Distances and walking times."""
from __future__ import annotations

import math

import numpy as np

from . import config

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def walk_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Street walking distance: straight line times a detour factor."""
    return haversine_km(lat1, lng1, lat2, lng2) * config.DETOUR_FACTOR


def walk_minutes(km: float) -> float:
    return km / config.WALK_SPEED_KMH * 60


def walk_matrix(points: list[tuple[float, float]]) -> np.ndarray:
    n = len(points)
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d[i, j] = d[j, i] = walk_km(*points[i], *points[j])
    return d
