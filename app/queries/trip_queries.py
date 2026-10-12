"""Raw SQL for trips and the day-wise itinerary (trip_places)."""
from app.queries.place_queries import HAVERSINE_SQL

TRIP_SELECT = """
    SELECT t.trip_id, t.user_id, t.city_id, c.name AS city,
           t.planned_budget, t.start_date, t.end_date, t.created_at
    FROM trips t
    JOIN cities c ON t.city_id = c.city_id
"""

STOP_SELECT = """
    SELECT tp.id, tp.trip_id, tp.place_id, p.name AS place_name, cat.name AS category,
           p.latitude, p.longitude, tp.day_number, tp.visit_order, tp.planned_cost
    FROM trip_places tp
    JOIN places p ON tp.place_id = p.place_id
    JOIN categories cat ON p.category_id = cat.category_id
"""


# ---------- Trips ----------

def create_trip(conn, user_id, city_id, planned_budget, start_date, end_date) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO trips (user_id, city_id, planned_budget, start_date, end_date) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, city_id, planned_budget, start_date, end_date),
        )
        conn.commit()
        return cursor.lastrowid


def get_trip(conn, trip_id: int):
    with conn.cursor() as cursor:
        cursor.execute(TRIP_SELECT + " WHERE t.trip_id = %s", (trip_id,))
        return cursor.fetchone()


def list_trips(conn, user_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            TRIP_SELECT + " WHERE t.user_id = %s ORDER BY t.created_at DESC, t.trip_id DESC",
            (user_id,),
        )
        return cursor.fetchall()


def delete_trip(conn, trip_id: int) -> None:
    """Child rows first (foreign keys), then the trip, all in ONE transaction."""
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM expenses WHERE trip_id = %s", (trip_id,))
        cursor.execute("DELETE FROM trip_places WHERE trip_id = %s", (trip_id,))
        cursor.execute("DELETE FROM trips WHERE trip_id = %s", (trip_id,))
        conn.commit()


def get_budget_summary(conn, trip_id: int):
    """Planned budget, itinerary cost and actual spend side by side (3 numbers, 1 query).
    Scalar subqueries are used so the two SUMs cannot multiply each other (a JOIN would)."""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT t.planned_budget,
                   COALESCE((SELECT SUM(planned_cost) FROM trip_places
                             WHERE trip_id = t.trip_id), 0) AS itinerary_cost,
                   COALESCE((SELECT SUM(amount) FROM expenses
                             WHERE trip_id = t.trip_id), 0) AS actual_spent
            FROM trips t
            WHERE t.trip_id = %s
            """,
            (trip_id,),
        )
        return cursor.fetchone()


# ---------- Stops (trip_places) ----------

def list_stops(conn, trip_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            STOP_SELECT + " WHERE tp.trip_id = %s ORDER BY tp.day_number, tp.visit_order, tp.id",
            (trip_id,),
        )
        return cursor.fetchall()


def get_stop(conn, trip_id: int, stop_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            STOP_SELECT + " WHERE tp.trip_id = %s AND tp.id = %s", (trip_id, stop_id)
        )
        return cursor.fetchone()


def next_visit_order(conn, trip_id: int, day_number: int) -> int:
    """Position at the end of a day: current max + 1 (or 1 for an empty day)."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(MAX(visit_order), 0) + 1 AS nxt FROM trip_places "
            "WHERE trip_id = %s AND day_number = %s",
            (trip_id, day_number),
        )
        return cursor.fetchone()["nxt"]


def shift_orders_from(conn, trip_id: int, day_number: int, from_order: int) -> None:
    """Make room: every stop at `from_order` or later moves one step down. No commit."""
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE trip_places SET visit_order = visit_order + 1 "
            "WHERE trip_id = %s AND day_number = %s AND visit_order >= %s",
            (trip_id, day_number, from_order),
        )


def insert_stop(conn, trip_id, place_id, day_number, visit_order, planned_cost) -> int:
    """No commit (the caller may do several steps in one transaction)."""
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO trip_places (trip_id, place_id, day_number, visit_order, planned_cost) "
            "VALUES (%s, %s, %s, %s, %s)",
            (trip_id, place_id, day_number, visit_order, planned_cost),
        )
        return cursor.lastrowid


def update_stop_fields(conn, stop_id: int, day_number, visit_order, planned_cost) -> None:
    """No commit."""
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE trip_places SET day_number = %s, visit_order = %s, planned_cost = %s "
            "WHERE id = %s",
            (day_number, visit_order, planned_cost, stop_id),
        )


def delete_stop(conn, stop_id: int) -> None:
    """No commit."""
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM trip_places WHERE id = %s", (stop_id,))


def renumber_day(conn, trip_id: int, day_number: int) -> None:
    """Close gaps: make visit_order exactly 1, 2, 3... for that day. No commit."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM trip_places WHERE trip_id = %s AND day_number = %s "
            "ORDER BY visit_order, id",
            (trip_id, day_number),
        )
        ids = [row["id"] for row in cursor.fetchall()]
        for position, stop_id in enumerate(ids, start=1):
            cursor.execute(
                "UPDATE trip_places SET visit_order = %s WHERE id = %s", (position, stop_id)
            )


def set_day_order(conn, stop_ids: list[int]) -> None:
    """First id in the list gets visit_order 1, the second 2, and so on. No commit."""
    with conn.cursor() as cursor:
        for position, stop_id in enumerate(stop_ids, start=1):
            cursor.execute(
                "UPDATE trip_places SET visit_order = %s WHERE id = %s", (position, stop_id)
            )


def get_first_stop_coords(conn, trip_id: int, day_number: int):
    """Latitude/longitude of the stop that is currently first in that day."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT p.latitude, p.longitude FROM trip_places tp "
            "JOIN places p ON tp.place_id = p.place_id "
            "WHERE tp.trip_id = %s AND tp.day_number = %s "
            "ORDER BY tp.visit_order, tp.id LIMIT 1",
            (trip_id, day_number),
        )
        return cursor.fetchone()


def optimize_day_by_distance(conn, trip_id: int, day_number: int, ref_lat, ref_lng) -> None:
    """ONE UPDATE that re-orders a whole day by Haversine distance from the reference point.

    The inner query numbers the stops 1, 2, 3... using the ROW_NUMBER() window function,
    ordered by distance. The outer UPDATE joins that numbering back onto trip_places.
    Tie-breaker `tp2.id` keeps the result stable when two places are equally far.
    """
    sql = (
        """
        UPDATE trip_places tp
        JOIN (
            SELECT tp2.id,
                   ROW_NUMBER() OVER (ORDER BY """ + HAVERSINE_SQL + """, tp2.id) AS new_order
            FROM trip_places tp2
            JOIN places p ON tp2.place_id = p.place_id
            WHERE tp2.trip_id = %s AND tp2.day_number = %s
        ) ranked ON tp.id = ranked.id
        SET tp.visit_order = ranked.new_order
        """
    )
    with conn.cursor() as cursor:
        cursor.execute(sql, (ref_lat, ref_lng, ref_lat, trip_id, day_number))
        conn.commit()
