from datetime import date, timedelta


def test_admin_overview_empty(client, admin_headers):
    data = client.get("/admin/overview", headers=admin_headers).json()
    assert data["total_users"] == 1 and data["cached_places"] == 0
    assert data["most_searched_city"] is None and data["most_saved_place"] is None


def test_admin_overview_with_data(client, sample_city, admin_headers, user_headers):
    pid = sample_city["places"]["Baga Beach"]
    client.post("/favorites", json={"place_id": pid}, headers=user_headers)
    client.get("/cities/Goa/places")
    client.get("/cities/Goa/places", headers=user_headers)

    data = client.get("/admin/overview", headers=admin_headers).json()
    assert data["total_users"] == 2 and data["cached_cities"] == 1 and data["cached_places"] == 4
    assert data["most_searched_city"] == {"name": "Goa", "search_count": 2}
    assert data["most_saved_place"] == {"name": "Baga Beach", "save_count": 1}


def test_activity_7d_has_no_missing_days(client, sample_city, admin_headers, user_headers, db):
    # One search today by a user, plus two searches 3 days ago by a user and a visitor
    client.get("/cities/Goa/places", headers=user_headers)
    with db.cursor() as cur:
        cur.execute("SELECT user_id FROM users WHERE email = 'asha@example.com'")
        uid = cur.fetchone()["user_id"]
        cur.execute("SELECT city_id FROM cities LIMIT 1")
        cid = cur.fetchone()["city_id"]
        cur.execute("INSERT INTO user_searches (user_id, city_id, searched_at) VALUES "
                    "(%s, %s, NOW() - INTERVAL 3 DAY), (NULL, %s, NOW() - INTERVAL 3 DAY)", (uid, cid, cid))
        # An old search (10 days ago) must NOT appear
        cur.execute("INSERT INTO user_searches (user_id, city_id, searched_at) VALUES (%s, %s, NOW() - INTERVAL 10 DAY)", (uid, cid))
    db.commit()

    rows = client.get("/admin/activity-7d", headers=admin_headers).json()
    assert len(rows) == 7
    today = date.today()
    assert [r["day"] for r in rows] == [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    by_day = {r["day"]: r for r in rows}
    assert by_day[today.isoformat()]["active_users"] == 1
    three_ago = by_day[(today - timedelta(days=3)).isoformat()]
    assert three_ago["searches"] == 2 and three_ago["active_users"] == 1      # visitor has no user_id
    assert sum(r["searches"] for r in rows) == 3
    assert sum(1 for r in rows if r["searches"] == 0) == 5                    # quiet days present as 0


def test_city_stats(client, sample_city, admin_headers):
    client.post("/cities", json={"name": "Empty City"}, headers=admin_headers)
    rows = client.get("/admin/city-stats", headers=admin_headers).json()
    goa = next(r for r in rows if r["city"] == "Goa")
    assert goa["cached_places"] == 4 and goa["top_category"] == "Attraction"
    assert goa["avg_cost"] == 2550.0
    empty = next(r for r in rows if r["city"] == "Empty City")
    assert empty["cached_places"] == 0 and empty["top_category"] is None and empty["avg_cost"] is None
    assert rows[0]["city"] == "Goa"                                           # sorted by place count


def test_admin_endpoints_need_admin(client, user_headers):
    for path in ("/admin/overview", "/admin/activity-7d", "/admin/city-stats"):
        assert client.get(path, headers=user_headers).status_code == 403
        assert client.get(path).status_code == 401
