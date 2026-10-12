"""Raw SQL for cities, categories, places, search logging and the stored procedure."""

# One SELECT reused everywhere. JOINs turn city_id / category_id into readable names.
PLACE_COLUMNS = """
    p.place_id, p.name, p.avg_cost, p.rating, p.latitude, p.longitude,
    c.name AS city, cat.name AS category
"""
PLACE_FROM = """
    FROM places p
    JOIN cities c ON p.city_id = c.city_id
    JOIN categories cat ON p.category_id = cat.category_id
"""

# Haversine formula: great-circle distance in km between (ref_lat, ref_lng) and a place.
# 6371 = Earth radius in km. The 3 %s placeholders are: ref_lat, ref_lng, ref_lat.
# LEAST/GREATEST clamp the value into [-1, 1]; tiny floating point errors could otherwise
# push it just outside that range and make ACOS return NULL (e.g. for the same point).
HAVERSINE_SQL = """(6371 * ACOS(LEAST(1, GREATEST(-1,
        COS(RADIANS(%s)) * COS(RADIANS(p.latitude))
        * COS(RADIANS(p.longitude) - RADIANS(%s))
        + SIN(RADIANS(%s)) * SIN(RADIANS(p.latitude))
    ))))"""

# Allowed values for sort. We map the user's choice to SQL text OURSELVES,
# so user input never becomes part of the SQL string.
ORDER_BY = {
    "rating": "(p.rating IS NULL), p.rating DESC, p.name",   # best first, unrated last
    "cost": "p.avg_cost ASC, p.name",
    "name": "p.name ASC",
    "distance": "distance_km ASC, p.place_id",
}


# ---------- Cities ----------

def get_all_cities(conn):
    with conn.cursor() as cursor:
        # "AS id" renames the column so it matches the NameOut schema
        cursor.execute("SELECT city_id AS id, name FROM cities ORDER BY name")
        return cursor.fetchall()


def get_city_by_name(conn, name: str):
    with conn.cursor() as cursor:
        cursor.execute("SELECT city_id, name FROM cities WHERE name = %s", (name,))
        return cursor.fetchone()


def get_city_by_id(conn, city_id: int):
    with conn.cursor() as cursor:
        cursor.execute("SELECT city_id, name FROM cities WHERE city_id = %s", (city_id,))
        return cursor.fetchone()


def create_city(conn, name: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO cities (name) VALUES (%s)", (name,))
        conn.commit()
        return cursor.lastrowid


def get_or_create_city(conn, name: str) -> int:
    """Insert the city, or return the id of the existing one. Does NOT commit."""
    with conn.cursor() as cursor:
        # LAST_INSERT_ID(city_id) trick: when the name already exists, the UPDATE part
        # sets LAST_INSERT_ID to the existing id, so lastrowid works in both cases.
        cursor.execute(
            "INSERT INTO cities (name) VALUES (%s) "
            "ON DUPLICATE KEY UPDATE city_id = LAST_INSERT_ID(city_id)",
            (name,),
        )
        return cursor.lastrowid


# ---------- Categories ----------

def get_all_categories(conn):
    with conn.cursor() as cursor:
        cursor.execute("SELECT category_id AS id, name FROM categories ORDER BY name")
        return cursor.fetchall()


def create_category(conn, name: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO categories (name) VALUES (%s)", (name,))
        conn.commit()
        return cursor.lastrowid


def get_category_ids_by_name(conn) -> dict:
    """{'hotel': 1, 'restaurant': 2, ...} (lowercase names) - used when saving API results."""
    with conn.cursor() as cursor:
        cursor.execute("SELECT category_id, name FROM categories")
        return {row["name"].lower(): row["category_id"] for row in cursor.fetchall()}


# ---------- Places ----------

def search_places(
    conn,
    *,
    city_id: int | None = None,
    city_name: str | None = None,
    category_id: int | None = None,
    category_name: str | None = None,
    min_rating: float | None = None,
    q: str | None = None,
    ref_lat: float | None = None,
    ref_lng: float | None = None,
    max_distance_km: float | None = None,
    sort: str = "rating",
    limit: int = 100,
    offset: int = 0,
):
    """One flexible query behind all the list/filter/nearby endpoints.

    A WHERE condition is added only when the matching argument was given.
    The condition TEXT is always our own fixed string; the VALUES go in `params`.
    """
    columns = PLACE_COLUMNS
    select_params: list = []
    where: list[str] = []
    where_params: list = []

    # The distance column exists only when a reference point was given
    has_distance = ref_lat is not None and ref_lng is not None
    if has_distance:
        columns += ", " + HAVERSINE_SQL + " AS distance_km"
        select_params += [ref_lat, ref_lng, ref_lat]

    if city_id is not None:
        where.append("p.city_id = %s")
        where_params.append(city_id)
    if city_name is not None:
        where.append("c.name = %s")
        where_params.append(city_name)
    if category_id is not None:
        where.append("p.category_id = %s")
        where_params.append(category_id)
    if category_name is not None:
        where.append("cat.name = %s")
        where_params.append(category_name)
    if min_rating is not None:
        where.append("p.rating >= %s")
        where_params.append(min_rating)
    if q:
        where.append("p.name LIKE %s")
        where_params.append(f"%{q}%")

    sql = "SELECT " + columns + PLACE_FROM
    if where:
        sql += " WHERE " + " AND ".join(where)

    having_params: list = []
    if has_distance and max_distance_km is not None:
        # HAVING (not WHERE) because it filters on the computed column distance_km
        sql += " HAVING distance_km <= %s"
        having_params.append(max_distance_km)

    order_key = sort if (sort != "distance" or has_distance) else "rating"
    sql += " ORDER BY " + ORDER_BY[order_key] + " LIMIT %s OFFSET %s"

    params = select_params + where_params + having_params + [limit, offset]
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def get_place_by_id(conn, place_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT " + PLACE_COLUMNS + PLACE_FROM + " WHERE p.place_id = %s", (place_id,)
        )
        return cursor.fetchone()


def create_place(conn, place) -> int:
    """`place` is a PlaceCreate object."""
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO places (name, avg_cost, rating, latitude, longitude, city_id, category_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (place.name, place.avg_cost, place.rating, place.latitude, place.longitude,
             place.city_id, place.category_id),
        )
        conn.commit()
        return cursor.lastrowid


def count_places_in_city(conn, city_id: int) -> int:
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n FROM places WHERE city_id = %s", (city_id,))
        return cursor.fetchone()["n"]


def insert_place_if_new(conn, city_id: int, category_id: int, item: dict) -> bool:
    """Insert one place fetched from the external API unless the same name already exists
    in that city. Does NOT commit (the caller commits once for the whole batch)."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT place_id FROM places WHERE city_id = %s AND name = %s",
            (city_id, item["name"]),
        )
        if cursor.fetchone():
            return False
        cursor.execute(
            "INSERT INTO places (name, avg_cost, rating, latitude, longitude, city_id, category_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (item["name"], item.get("avg_cost", 0), item.get("rating"),
             item["latitude"], item["longitude"], city_id, category_id),
        )
        return True


def best_value_places(conn, city_id: int, max_cost: float):
    """Calls the stored procedure from sql/procedures.sql."""
    with conn.cursor() as cursor:
        cursor.execute("CALL GetBestValuePlaces(%s, %s)", (city_id, max_cost))
        rows = cursor.fetchall()
        # A CALL can return extra result sets (like a status packet). Read them all
        # so the connection is clean for the next statement.
        while cursor.nextset():
            pass
        return rows


# ---------- Search log (feeds the admin analytics) ----------

def log_search(conn, user_id: int | None, city_id: int) -> None:
    """user_id is None for visitors who are not logged in (the column allows NULL)."""
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO user_searches (user_id, city_id) VALUES (%s, %s)", (user_id, city_id)
        )
        conn.commit()


# ---------- Advisory locks (used by the cache-aside flow) ----------

def acquire_lock(conn, lock_name: str, timeout_seconds: int) -> bool:
    """GET_LOCK waits up to `timeout_seconds` for the named lock.
    Returns 1 if we got it, 0 on timeout. The lock belongs to THIS connection."""
    with conn.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, %s) AS got", (lock_name, timeout_seconds))
        return cursor.fetchone()["got"] == 1


def release_lock(conn, lock_name: str) -> None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT RELEASE_LOCK(%s) AS released", (lock_name,))
        cursor.fetchone()
