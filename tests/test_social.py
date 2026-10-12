"""Favourites, recommendations (self-join) and reviews."""


def test_favorites_flow(client, sample_city, user_headers):
    ids = sample_city["places"]
    pid = ids["Baga Beach"]
    assert client.post("/favorites", json={"place_id": pid}, headers=user_headers).status_code == 201
    assert client.post("/favorites", json={"place_id": pid}, headers=user_headers).status_code == 400
    assert client.post("/favorites", json={"place_id": 9999}, headers=user_headers).status_code == 404
    assert client.post("/favorites", json={"place_id": pid}).status_code == 401

    favs = client.get("/favorites", headers=user_headers).json()
    assert [f["name"] for f in favs] == ["Baga Beach"]
    assert client.delete(f"/favorites/{pid}", headers=user_headers).status_code == 204
    assert client.delete(f"/favorites/{pid}", headers=user_headers).status_code == 404
    assert client.get("/favorites", headers=user_headers).json() == []


def test_saved_together_self_join(client, sample_city, user_headers, user2_headers):
    ids = sample_city["places"]
    baga, cal, taj, wharf = (ids[n] for n in ("Baga Beach", "Calangute Beach", "Taj Fort Aguada", "Fisherman's Wharf"))

    # Not enough history yet
    empty = client.get(f"/places/{baga}/recommendations").json()
    assert empty["recommendations"] == [] and empty["message"] == "Not enough favorite history yet"

    # user 1 saves Baga + Calangute + Taj ; user 2 saves Baga + Calangute + Wharf
    for headers, pids in ((user_headers, (baga, cal, taj)), (user2_headers, (baga, cal, wharf))):
        for pid in pids:
            client.post("/favorites", json={"place_id": pid}, headers=headers)

    rec = client.get(f"/places/{baga}/recommendations").json()
    by_name = {r["name"]: r["co_count"] for r in rec["recommendations"]}
    # Calangute was saved together with Baga by 2 users; Taj and Wharf by 1 each
    assert by_name == {"Calangute Beach": 2, "Taj Fort Aguada": 1, "Fisherman's Wharf": 1}
    assert rec["recommendations"][0]["name"] == "Calangute Beach"
    assert rec["message"] is None
    assert client.get("/places/99999/recommendations").status_code == 404


def test_reviews_flow(client, sample_city, user_headers, user2_headers):
    pid = sample_city["places"]["Baga Beach"]
    url = f"/places/{pid}/reviews"

    assert client.get(url).json()["review_count"] == 0
    assert client.get(url).json()["average_rating"] is None

    r1 = client.post(url, json={"rating": 4, "comment": "Nice"}, headers=user_headers)
    assert r1.status_code == 201 and r1.json()["user_name"] == "Asha"
    assert client.post(url, json={"rating": 5}, headers=user_headers).status_code == 400   # one per user
    client.post(url, json={"rating": 5, "comment": "Great"}, headers=user2_headers)
    assert client.post(url, json={"rating": 9}, headers=user2_headers).status_code == 422

    data = client.get(url).json()
    assert data["review_count"] == 2 and data["average_rating"] == 4.5

    rid = r1.json()["id"]
    assert client.put(f"/reviews/{rid}", json={"rating": 3, "comment": "Meh"}, headers=user2_headers).status_code == 403
    assert client.put(f"/reviews/{rid}", json={"rating": 3, "comment": "Meh"}, headers=user_headers).json()["rating"] == 3
    assert client.delete(f"/reviews/{rid}", headers=user2_headers).status_code == 403
    assert client.delete(f"/reviews/{rid}", headers=user_headers).status_code == 204
    assert client.get(url).json()["review_count"] == 1
    assert client.get("/places/9999/reviews").status_code == 404
