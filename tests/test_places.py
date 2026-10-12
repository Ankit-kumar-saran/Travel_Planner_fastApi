import threading

from app.services import place_provider

FAKE_ITEMS = [
    {"name": "Hotel Sea View", "category": "Hotel", "rating": 4.1, "avg_cost": 2500,
     "latitude": 12.9141, "longitude": 74.8560},
    {"name": "Fish Land", "category": "Restaurant", "rating": 4.6, "avg_cost": 600,
     "latitude": 12.8700, "longitude": 74.8400},
    {"name": "Panambur Beach", "category": "Attraction", "rating": 4.4, "avg_cost": 0,
     "latitude": 12.9500, "longitude": 74.8100},
]


def test_place_crud_and_filters(client, sample_city):
    ids, cats = sample_city["places"], sample_city["cats"]
    one = client.get(f"/places/{ids['Baga Beach']}").json()
    assert one["city"] == "Goa" and one["category"] == "Attraction" and one["rating"] == 4.5

    assert len(client.get("/places").json()) == 4
    assert len(client.get(f"/places?category_id={cats['Hotel']}").json()) == 1
    assert len(client.get("/places?min_rating=4.4").json()) == 2          # 4.5 and 4.8
    assert [p["name"] for p in client.get("/places?q=beach").json()] == ["Baga Beach", "Calangute Beach"]
    assert client.get("/places?sort=cost").json()[0]["avg_cost"] == 0
    assert client.get("/places/99999").status_code == 404


def test_create_place_errors(client, admin_headers, sample_city):
    bad_fk = {"name": "X Place", "latitude": 1, "longitude": 1, "city_id": 999, "category_id": 999}
    assert client.post("/places", json=bad_fk, headers=admin_headers).status_code == 400
    assert client.post("/places", json={**bad_fk, "latitude": 95}, headers=admin_headers).status_code == 422
    assert client.post("/cities", json={"name": "Goa"}, headers=admin_headers).status_code == 400


def test_nearby_haversine(client, sample_city):
    # Stand on Baga Beach: itself ~0 km, Calangute ~1.5 km, Fort Aguada ~7 km, Wharf ~27 km
    res = client.get("/places/nearby?lat=15.5566&lng=73.7517&radius_km=10").json()
    names = [p["name"] for p in res]
    assert names == ["Baga Beach", "Calangute Beach", "Taj Fort Aguada"]
    assert res[0]["distance_km"] < 0.01
    assert 1 < res[1]["distance_km"] < 2.5
    assert 5 < res[2]["distance_km"] < 9
    assert len(client.get("/places/nearby?lat=15.5566&lng=73.7517&radius_km=100").json()) == 4


def test_best_value_stored_procedure(client, sample_city):
    city_id = sample_city["city"]["id"]
    res = client.get(f"/places/best-value?city_id={city_id}&max_cost=2000").json()
    # Only the Wharf has a cost > 0 within budget (free places have NULL value_score)
    assert res[0]["name"] == "Fisherman's Wharf" and res[0]["value_score"] > 0
    assert all(p["avg_cost"] <= 2000 for p in res)


def test_cache_aside_hits_api_only_once(client, db, monkeypatch):
    calls = []

    def fake_fetch(city_name):
        calls.append(city_name)
        return FAKE_ITEMS

    monkeypatch.setattr(place_provider, "fetch_city_places", fake_fetch)

    first = client.get("/cities/Mangalore/places").json()
    assert first["source"] == "api" and first["count"] == 3
    second = client.get("/cities/Mangalore/places").json()
    assert second["source"] == "cache" and second["count"] == 3
    assert calls == ["Mangalore"]                       # API called exactly once

    # Filters work on the cached data
    only_hotels = client.get("/cities/Mangalore/places?category=Hotel").json()
    assert [p["name"] for p in only_hotels["places"]] == ["Hotel Sea View"]
    assert client.get("/cities/Mangalore/places?min_rating=4.5").json()["count"] == 1
    near = client.get("/cities/Mangalore/places?sort=distance&ref_lat=12.9141&ref_lng=74.8560").json()
    assert near["places"][0]["name"] == "Hotel Sea View"
    assert near["places"][0]["distance_km"] < 0.01

    # Every search was logged
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM user_searches")
        assert cur.fetchone()["n"] == 5


def test_concurrent_first_searches_call_api_once(client, db, monkeypatch):
    """The advisory lock: 4 simultaneous first searches -> exactly ONE API call, no duplicates."""
    import time
    calls = []

    def slow_fetch(city_name):
        calls.append(city_name)
        time.sleep(1.0)                   # long enough for the other threads to queue up
        return FAKE_ITEMS

    monkeypatch.setattr(place_provider, "fetch_city_places", slow_fetch)
    results = []

    def worker():
        results.append(client.get("/cities/Udupi/places").json())

    threads = [threading.Thread(target=worker) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]

    assert len(calls) == 1
    assert sorted(r["source"] for r in results) == ["api", "cache", "cache", "cache"]
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM places")
        assert cur.fetchone()["n"] == 3     # no duplicate rows


def test_unknown_city_and_provider_failure(client, monkeypatch):
    monkeypatch.setattr(place_provider, "fetch_city_places", lambda name: [])
    assert client.get("/cities/Atlantis/places").status_code == 404

    def boom(name):
        raise place_provider.ProviderError("down")

    monkeypatch.setattr(place_provider, "fetch_city_places", boom)
    assert client.get("/cities/Paris/places").status_code == 502
    # After a failure the lock is released, so a retry works
    monkeypatch.setattr(place_provider, "fetch_city_places", lambda name: FAKE_ITEMS)
    assert client.get("/cities/Paris/places").json()["source"] == "api"


def test_search_params_validation(client):
    assert client.get("/cities/Goa/places?sort=distance").status_code == 422
    assert client.get("/cities/Goa/places?ref_lat=10").status_code == 422
