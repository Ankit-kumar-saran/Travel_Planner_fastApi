"""Test setup. The tests run against a REAL MySQL database (not mocks), because the whole
point of this project is the SQL. Use a separate database so your real data is never touched.

Create it once:
    CREATE DATABASE wandersync_test;
    mysql -u root -p wandersync_test < sql/schema.sql
    mysql -u root -p wandersync_test < sql/procedures.sql
Then set TEST_DB_USER / TEST_DB_PASSWORD / TEST_DB_NAME (defaults below) and run:  pytest
"""
import os

# These must be set BEFORE `app` is imported, because app.config reads them at import time.
os.environ["DB_USER"] = os.getenv("TEST_DB_USER", "ws_test")
os.environ["DB_PASSWORD"] = os.getenv("TEST_DB_PASSWORD", "ws_test_pw")
os.environ["DB_NAME"] = os.getenv("TEST_DB_NAME", "wandersync_test")
os.environ["DB_HOST"] = os.getenv("TEST_DB_HOST", "localhost")
os.environ["JWT_SECRET"] = "test-secret-not-for-production"
os.environ["GOOGLE_PLACES_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""

import pytest
from fastapi.testclient import TestClient

from app.database import get_connection
from app.main import app

TABLES_TO_CLEAR = [
    "password_resets", "expenses", "trip_places", "trips", "reviews", "favorites",
    "user_searches", "places", "cities", "users",
]


@pytest.fixture(autouse=True)
def clean_database():
    """Empty every table before each test (categories keep their seed rows)."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in TABLES_TO_CLEAR:
            cur.execute(f"TRUNCATE TABLE {table}")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        cur.execute("INSERT IGNORE INTO categories (name) VALUES ('Hotel'),('Restaurant'),('Attraction')")
    conn.commit()
    conn.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    conn = get_connection()
    yield conn
    conn.close()


def register_and_login(client, name="Asha", email="asha@example.com", password="secret123"):
    client.post("/auth/register", json={"name": name, "email": email, "password": password})
    res = client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def user_headers(client):
    return register_and_login(client)


@pytest.fixture
def user2_headers(client):
    return register_and_login(client, "Ravi", "ravi@example.com")


@pytest.fixture
def admin_headers(client, db):
    headers = register_and_login(client, "Boss", "boss@example.com")
    with db.cursor() as cur:
        cur.execute("UPDATE users SET role = 'admin' WHERE email = 'boss@example.com'")
    db.commit()
    return headers


@pytest.fixture
def sample_city(client, admin_headers):
    """A city with 4 places near Goa, so tests have data to work with."""
    city = client.post("/cities", json={"name": "Goa"}, headers=admin_headers).json()
    cats = {c["name"]: c["id"] for c in client.get("/categories").json()}
    spots = [
        ("Baga Beach", 0, 4.5, 15.5566, 73.7517, "Attraction"),
        ("Calangute Beach", 0, 4.2, 15.5440, 73.7550, "Attraction"),
        ("Taj Fort Aguada", 9000, 4.8, 15.4930, 73.7730, "Hotel"),
        ("Fisherman's Wharf", 1200, 4.0, 15.2993, 73.9620, "Restaurant"),
    ]
    ids = {}
    for name, cost, rating, lat, lng, cat in spots:
        res = client.post("/places", headers=admin_headers, json={
            "name": name, "avg_cost": cost, "rating": rating, "latitude": lat,
            "longitude": lng, "city_id": city["id"], "category_id": cats[cat],
        })
        assert res.status_code == 201, res.text
        ids[name] = res.json()["place_id"]
    return {"city": city, "places": ids, "cats": cats}
