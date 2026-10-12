"""Trips, day-wise itinerary, distance optimisation and expenses."""


def make_trip(client, headers, city_id, budget=10000):
    res = client.post("/trips", headers=headers, json={
        "city_id": city_id, "planned_budget": budget,
        "start_date": "2026-12-01", "end_date": "2026-12-03",
    })
    assert res.status_code == 201, res.text
    return res.json()["trip_id"]


def add_stop(client, headers, trip_id, place_id, day=1, **extra):
    res = client.post(f"/trips/{trip_id}/places", headers=headers,
                      json={"place_id": place_id, "day_number": day, **extra})
    assert res.status_code == 201, res.text
    return res.json()


def test_trip_crud_and_ownership(client, sample_city, user_headers, user2_headers):
    city_id = sample_city["city"]["id"]
    trip_id = make_trip(client, user_headers, city_id)

    assert client.post("/trips", headers=user_headers, json={"city_id": 999}).status_code == 404
    bad_dates = {"city_id": city_id, "start_date": "2026-12-05", "end_date": "2026-12-01"}
    assert client.post("/trips", headers=user_headers, json=bad_dates).status_code == 422
    assert client.post("/trips", json={"city_id": city_id}).status_code == 401

    assert len(client.get("/trips", headers=user_headers).json()) == 1
    assert client.get("/trips", headers=user2_headers).json() == []
    # Somebody else's trip: 403 on read, write and delete
    assert client.get(f"/trips/{trip_id}", headers=user2_headers).status_code == 403
    assert client.delete(f"/trips/{trip_id}", headers=user2_headers).status_code == 403
    assert client.get("/trips/9999", headers=user_headers).status_code == 404
    assert client.delete(f"/trips/{trip_id}", headers=user_headers).status_code == 204
    assert client.get(f"/trips/{trip_id}", headers=user_headers).status_code == 404


def test_stops_order_edit_delete(client, sample_city, user_headers):
    p = sample_city["places"]
    trip_id = make_trip(client, user_headers, sample_city["city"]["id"])

    a = add_stop(client, user_headers, trip_id, p["Baga Beach"], day=1)
    b = add_stop(client, user_headers, trip_id, p["Calangute Beach"], day=1)
    c = add_stop(client, user_headers, trip_id, p["Taj Fort Aguada"], day=1, planned_cost=5000)
    assert [a["visit_order"], b["visit_order"], c["visit_order"]] == [1, 2, 3]
    assert a["planned_cost"] == 0 and c["planned_cost"] == 5000     # default = place avg_cost

    # Insert at position 1: the others shift down
    d = add_stop(client, user_headers, trip_id, p["Fisherman's Wharf"], day=1, visit_order=1)
    order = [(s["place_name"], s["visit_order"]) for s in client.get(f"/trips/{trip_id}", headers=user_headers).json()["stops"]]
    assert order == [("Fisherman's Wharf", 1), ("Baga Beach", 2), ("Calangute Beach", 3), ("Taj Fort Aguada", 4)]

    # Move a stop to day 2: both days are renumbered without gaps
    moved = client.patch(f"/trips/{trip_id}/places/{a['id']}", headers=user_headers, json={"day_number": 2}).json()
    assert moved["day_number"] == 2 and moved["visit_order"] == 1
    day1 = [s for s in client.get(f"/trips/{trip_id}", headers=user_headers).json()["stops"] if s["day_number"] == 1]
    assert [s["visit_order"] for s in day1] == [1, 2, 3]

    # Edit the cost, delete a stop
    assert client.patch(f"/trips/{trip_id}/places/{b['id']}", headers=user_headers, json={"planned_cost": 99}).json()["planned_cost"] == 99
    assert client.delete(f"/trips/{trip_id}/places/{d['id']}", headers=user_headers).status_code == 204
    day1 = [s for s in client.get(f"/trips/{trip_id}", headers=user_headers).json()["stops"] if s["day_number"] == 1]
    assert [s["visit_order"] for s in day1] == [1, 2]
    assert client.delete(f"/trips/{trip_id}/places/{d['id']}", headers=user_headers).status_code == 404
    assert client.post(f"/trips/{trip_id}/places", headers=user_headers, json={"place_id": 9999, "day_number": 1}).status_code == 404
    assert client.post(f"/trips/{trip_id}/places", headers=user_headers, json={"place_id": p["Baga Beach"], "day_number": 0}).status_code == 422


def test_manual_reorder(client, sample_city, user_headers):
    p = sample_city["places"]
    trip_id = make_trip(client, user_headers, sample_city["city"]["id"])
    s = [add_stop(client, user_headers, trip_id, p[n]) for n in ("Baga Beach", "Calangute Beach", "Taj Fort Aguada")]
    ids = [x["id"] for x in s]

    res = client.put(f"/trips/{trip_id}/days/1/order", headers=user_headers, json={"stop_ids": [ids[2], ids[0], ids[1]]})
    assert [x["place_name"] for x in res.json()] == ["Taj Fort Aguada", "Baga Beach", "Calangute Beach"]
    # Missing / foreign / duplicate ids are refused
    assert client.put(f"/trips/{trip_id}/days/1/order", headers=user_headers, json={"stop_ids": ids[:2]}).status_code == 400
    assert client.put(f"/trips/{trip_id}/days/1/order", headers=user_headers, json={"stop_ids": ids + [999]}).status_code == 400


def test_optimize_by_distance(client, sample_city, user_headers):
    p = sample_city["places"]
    trip_id = make_trip(client, user_headers, sample_city["city"]["id"])
    # Added in a deliberately bad order: far, near, mid, nearest
    for name in ("Fisherman's Wharf", "Taj Fort Aguada", "Calangute Beach", "Baga Beach"):
        add_stop(client, user_headers, trip_id, p[name])

    # From Baga Beach: Baga (0) -> Calangute (~1.5) -> Taj (~7) -> Wharf (~27)
    res = client.post(f"/trips/{trip_id}/days/1/optimize", headers=user_headers,
                      json={"ref_lat": 15.5566, "ref_lng": 73.7517})
    assert [s["place_name"] for s in res.json()] == ["Baga Beach", "Calangute Beach", "Taj Fort Aguada", "Fisherman's Wharf"]
    assert [s["visit_order"] for s in res.json()] == [1, 2, 3, 4]

    # Without a reference point it starts from the current first stop (Baga Beach now)
    res = client.post(f"/trips/{trip_id}/days/1/optimize", headers=user_headers)
    assert res.status_code == 200 and res.json()[0]["place_name"] == "Baga Beach"
    assert client.post(f"/trips/{trip_id}/days/7/optimize", headers=user_headers).status_code == 404
    assert client.post(f"/trips/{trip_id}/days/1/optimize", headers=user_headers, json={"ref_lat": 10}).status_code == 422


def test_expenses_and_budget(client, sample_city, user_headers, user2_headers):
    p = sample_city["places"]
    trip_id = make_trip(client, user_headers, sample_city["city"]["id"], budget=10000)
    add_stop(client, user_headers, trip_id, p["Taj Fort Aguada"])                  # 9000 planned
    add_stop(client, user_headers, trip_id, p["Fisherman's Wharf"])                # 1200 planned

    url = f"/trips/{trip_id}/expenses"
    e1 = client.post(url, headers=user_headers, json={"amount": 4000, "category": "Travel", "spent_date": "2026-12-01"})
    client.post(url, headers=user_headers, json={"amount": 1500.5, "category": "Food", "spent_date": "2026-12-02", "note": "dinner"})
    client.post(url, headers=user_headers, json={"amount": 500, "category": "Food", "spent_date": "2026-12-02"})
    assert e1.status_code == 201

    assert client.post(url, headers=user_headers, json={"amount": -5, "spent_date": "2026-12-01"}).status_code == 422
    assert client.post(url, headers=user_headers, json={"amount": 5, "category": "Gold", "spent_date": "2026-12-01"}).status_code == 422
    assert client.get(url, headers=user2_headers).status_code == 403
    assert client.post(url, headers=user2_headers, json={"amount": 5, "spent_date": "2026-12-01"}).status_code == 403

    budget = client.get(f"/trips/{trip_id}/budget", headers=user_headers).json()
    # The two SUMs must not multiply each other (3 expenses x 2 stops)
    assert budget == {"planned_budget": 10000.0, "itinerary_cost": 10200.0, "actual_spent": 6000.5,
                      "remaining": 3999.5, "percent_spent": 60.0}

    summary = client.get(f"{url}/summary", headers=user_headers).json()
    assert summary == [{"category": "Travel", "total": 4000.0}, {"category": "Food", "total": 2000.5}]
    listing = client.get(url, headers=user_headers).json()
    assert len(listing) == 3 and listing[0]["spent_date"] == "2026-12-02"

    assert client.delete(f"{url}/{e1.json()['id']}", headers=user_headers).status_code == 204
    assert client.delete(f"{url}/{e1.json()['id']}", headers=user_headers).status_code == 404
    assert client.get(f"/trips/{trip_id}/budget", headers=user_headers).json()["actual_spent"] == 2000.5

    # Deleting the trip removes its stops and expenses too (no foreign-key error)
    assert client.delete(f"/trips/{trip_id}", headers=user_headers).status_code == 204


def test_zero_budget_does_not_divide_by_zero(client, sample_city, user_headers):
    trip_id = make_trip(client, user_headers, sample_city["city"]["id"], budget=0)
    assert client.get(f"/trips/{trip_id}/budget", headers=user_headers).json()["percent_spent"] == 0.0
