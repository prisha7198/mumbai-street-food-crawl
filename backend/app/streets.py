"""Real walking routes along streets, for display.

The recommender itself plans with straight-line distance x 1.3 (geo.py), so
it stays fast, deterministic and fully offline. Once a crawl is chosen, this
module asks an OSRM walking router (OpenStreetMap data) for the actual path
of each leg, so the map can draw the line along streets and the walk times
shown to the user are real.

Every leg is fetched separately and cached, so a swap only fetches the two
legs that changed. If the router is unreachable, callers get None for that
leg and the map falls back to a straight line. After a failure we stop
asking for a short while, so an offline demo never waits on the network.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import config

log = logging.getLogger("crawl.streets")
_cache: dict[tuple, dict | None] = {}
_lock = threading.Lock()
_down_until = 0.0
_pool = ThreadPoolExecutor(max_workers=6)


def available() -> bool:
    return config.USE_STREET_ROUTING and time.monotonic() >= _down_until


def _key(a: tuple[float, float], b: tuple[float, float]) -> tuple:
    return (round(a[0], 5), round(a[1], 5), round(b[0], 5), round(b[1], 5))


def _fetch(a: tuple[float, float], b: tuple[float, float]) -> dict | None:
    import httpx

    url = f"{config.STREET_ROUTING_URL}/{a[1]},{a[0]};{b[1]},{b[0]}"
    r = httpx.get(
        url,
        params={"overview": "full", "geometries": "geojson", "steps": "false"},
        headers={"User-Agent": config.STREET_ROUTING_USER_AGENT},
        timeout=config.STREET_ROUTING_TIMEOUT_S,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError(f"router answered {data.get('code')}")
    route = data["routes"][0]
    coords = [[lat, lng] for lng, lat in route["geometry"]["coordinates"]]
    # the router snaps to the nearest street; join the line to the stalls themselves
    coords = [[a[0], a[1]], *coords, [b[0], b[1]]]
    return {"coords": coords, "distance_m": float(route["distance"]), "duration_min": float(route["duration"]) / 60}


def walking_leg(a: tuple[float, float], b: tuple[float, float]) -> dict | None:
    global _down_until
    k = _key(a, b)
    if k in _cache:
        return _cache[k]
    if not available():
        return None
    try:
        leg = _fetch(a, b)
    except Exception as e:  # noqa: BLE001 - routing is decoration; never fail the request
        log.warning("Street routing unavailable (%s); drawing straight lines for %ss", e, config.STREET_ROUTING_COOLDOWN_S)
        _down_until = time.monotonic() + config.STREET_ROUTING_COOLDOWN_S
        return None
    with _lock:
        if len(_cache) > 5000:
            _cache.clear()
        _cache[k] = leg
    return leg


def walking_legs(points: list[tuple[float, float]]) -> list[dict | None]:
    """One entry per consecutive pair of points, fetched in parallel."""
    pairs = list(zip(points, points[1:]))
    if not pairs:
        return []
    return list(_pool.map(lambda ab: walking_leg(*ab), pairs))
