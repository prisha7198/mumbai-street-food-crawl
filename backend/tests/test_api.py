import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_meta():
    assert client.get("/api/health").json()["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert len(meta["areas"]) >= 5
    assert all({"name", "lat", "lng"} <= set(a) for a in meta["areas"])
    assert meta["profiles"]


def test_stalls_endpoints():
    stalls = client.get("/api/stalls").json()["stalls"]
    assert stalls
    one = client.get(f"/api/stalls/{stalls[0]['id']}").json()
    assert one["id"] == stalls[0]["id"] and "status" in one
    assert client.get("/api/stalls/nope").status_code == 404


def test_intent_endpoint():
    r = client.post("/api/intent", json={"text": "4 spicy veg stops near Dadar under ₹400"}).json()
    assert r["parser_used"] == "rules"
    assert r["preferences"]["area"] == "Dadar" and r["preferences"]["diet"] == "veg"


def test_recommend_happy_path():
    body = {"text": "4 spicy veg stops near Dadar under ₹400, something sweet at the end",
            "preferences": {"time": "20:00", "day": "Friday"}}
    t = time.perf_counter()
    r = client.post("/api/recommend", json=body)
    elapsed = (time.perf_counter() - t) * 1000
    assert r.status_code == 200
    data = r.json()
    stops = data["stops"]
    assert len(stops) == 4
    assert [s["order"] for s in stops] == [1, 2, 3, 4]
    assert all(s["stall"]["veg_type"] != "non_veg" for s in stops)
    assert stops[-1]["stall"]["category"] in ("kulfi_desserts", "juice_falooda")
    assert all(s["why"] and len(s["why"].split()) <= 18 for s in stops)
    assert data["totals"]["walk_km"] <= data["preferences"]["max_walk_km"] + 1e-6
    for key in ("filters", "scoring", "diversity", "routing", "understood"):
        assert key in data["trace"]
    assert data["trace"]["parser_used"] == "rules"
    assert elapsed < 300, f"took {elapsed:.0f} ms"


def test_swap_excludes_and_pins():
    body = {"text": "late night non veg on Mohammed Ali Road", "preferences": {"day": "Friday"}}
    first = client.post("/api/recommend", json=body).json()
    ids = [s["stall"]["id"] for s in first["stops"]]
    swapped = client.post("/api/recommend", json={**body, "exclude_ids": [ids[0]], "pinned_ids": ids[1:]}).json()
    new_ids = [s["stall"]["id"] for s in swapped["stops"]]
    assert ids[0] not in new_ids
    assert set(ids[1:]) <= set(new_ids)


def test_impossible_request_gives_actionable_notice():
    body = {"text": "10 stops in Colaba at 3 AM under ₹50", "preferences": {"day": "Friday"}}
    data = client.post("/api/recommend", json=body).json()
    assert data["stops"] == []
    notice = data["notice"]
    assert notice and notice["kind"] == "empty"
    assert notice["action"] and notice["action"]["patch"]
    # applying the suggestion should actually produce stops
    fixed = client.post("/api/recommend", json={**body, "preferences": {**body["preferences"],
                                                                         **notice["action"]["patch"]}}).json()
    assert len(fixed["stops"]) > 0


def test_profile_enables_cf():
    meta = client.get("/api/meta").json()
    pid = meta["profiles"][0]["id"]
    data = client.post("/api/recommend", json={"text": "chaat in Ghatkopar", "profile_id": pid,
                                               "preferences": {"time": "20:00", "day": "Friday"}}).json()
    assert data["trace"]["scoring"]["cf_active"] is True
    assert data["trace"]["scoring"]["weights"]["cf"] > 0
