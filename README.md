# WanderSync Backend

A smart travel planner API built with **FastAPI** and **MySQL** (raw SQL with `pymysql`, no ORM).

The database does the hard work: a MySQL cache for city data, advisory locks, Haversine distance
sorting, a self-join recommender, a recursive CTE for analytics and a stored procedure.

## Features

| Feature | Where the SQL lives | Advanced SQL used |
|---|---|---|
| Register / login (bcrypt + JWT), password reset by email | `queries/user_queries.py` | hashed one-time tokens, 30 min expiry |
| City search with cache (`GET /cities/{name}/places`) | `services/city_cache.py` | **cache-aside + `GET_LOCK()`**, `ON DUPLICATE KEY UPDATE` |
| Filter and sort places (category, rating, name, cost) | `queries/place_queries.py` | dynamic `WHERE` with `%s` placeholders |
| Nearby places / sort by distance | `queries/place_queries.py` | **Haversine formula** in SQL |
| Favourites + "Frequently saved together" | `queries/favorite_queries.py` | **self-join** + `GROUP BY` |
| Reviews with average rating | `queries/review_queries.py` | `AVG`, `COUNT` |
| Trips, day-wise itinerary, manual reorder | `queries/trip_queries.py` | transactions |
| Optimise a day by distance | `queries/trip_queries.py` | `UPDATE ... JOIN` + **`ROW_NUMBER()`** window function |
| Expenses and budget bar | `queries/expense_queries.py` | scalar subqueries, `GROUP BY` |
| Best value places | `sql/procedures.sql` | **stored procedure** |
| Admin dashboard | `queries/admin_queries.py` | **recursive CTE** (7 days, no gaps), correlated subquery |

## Project structure

```
wandersync-backend/
├── app/
│   ├── main.py            # creates the app, CORS, includes all routers
│   ├── config.py          # reads .env (pydantic-settings)
│   ├── database.py        # MySQL connection + get_db dependency
│   ├── core/              # security.py (bcrypt, JWT), dependencies.py (login / admin checks)
│   ├── schemas/           # Pydantic request and response shapes
│   ├── queries/           # ALL raw SQL (one file per feature)
│   ├── services/          # external API, cache-aside logic, email
│   └── routers/           # the HTTP endpoints
├── sql/
│   ├── schema.sql         # all tables + category seed (safe to re-run)
│   └── procedures.sql     # stored procedure GetBestValuePlaces
├── tests/                 # 29 tests, run against a real MySQL database
├── .env.example           # copy to .env
└── requirements.txt
```

## Setup

```bash
# 1. Install
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env                # then edit .env (see "Before you push" below)

# 3. Database (as MySQL root, in database "wandersync")
mysql -u root -p wandersync < sql/schema.sql
mysql -u root -p wandersync < sql/procedures.sql
mysql -u root -p -e "GRANT EXECUTE ON wandersync.* TO 'wandersync_user'@'localhost';"

# 4. Run
uvicorn app.main:app --reload       # open http://127.0.0.1:8000/docs
```

### Make yourself an admin

Admin routes (`/admin/*`, creating cities, categories and places by hand) need `role = 'admin'`.
Register normally, then run once in MySQL:

```sql
UPDATE users SET role = 'admin' WHERE email = 'your@email.com';
```

Log in again to get a token (the role is also stored in the token).

## Tests

The tests use a **separate** database so your real data is never touched.

```sql
CREATE DATABASE wandersync_test;
CREATE USER 'ws_test'@'localhost' IDENTIFIED BY 'ws_test_pw';
GRANT ALL ON wandersync_test.* TO 'ws_test'@'localhost';
```
```bash
mysql -u root -p wandersync_test < sql/schema.sql
mysql -u root -p wandersync_test < sql/procedures.sql
pytest
```

To use other credentials, set `TEST_DB_USER`, `TEST_DB_PASSWORD`, `TEST_DB_NAME` first.
The tests wipe the tables of the test database before every test.

## Main endpoints

Open `/docs` for the full interactive list. The most important ones:

- `POST /auth/register`, `POST /auth/login`, `POST /auth/forgot-password`, `POST /auth/reset-password`
- `GET /cities/{name}/places?category=&min_rating=&sort=rating|cost|name|distance&ref_lat=&ref_lng=`
- `GET /places/nearby?lat=&lng=&radius_km=`, `GET /places/{id}`, `GET /places/{id}/recommendations`
- `POST /favorites`, `DELETE /favorites/{place_id}`, `GET /favorites`
- `GET/POST /places/{id}/reviews`
- `POST /trips`, `POST /trips/{id}/places`, `PUT /trips/{id}/days/{n}/order`, `POST /trips/{id}/days/{n}/optimize`
- `POST /trips/{id}/expenses`, `GET /trips/{id}/budget`
- `GET /admin/overview`, `/admin/activity-7d`, `/admin/city-stats` (admin only)

## Before you push to GitHub

See the checklist at the end of the chat message that came with this project. In short:
create your `.env` from `.env.example`, never commit `.env`, and change `JWT_SECRET`.
