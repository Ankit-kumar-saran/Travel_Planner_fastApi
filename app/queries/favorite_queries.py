"""Raw SQL for favourites and the "Frequently Saved Together" recommendation."""
from app.queries.place_queries import PLACE_COLUMNS, PLACE_FROM


def get_favorite(conn, user_id: int, place_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id FROM favorites WHERE user_id = %s AND place_id = %s", (user_id, place_id)
        )
        return cursor.fetchone()


def add_favorite(conn, user_id: int, place_id: int) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO favorites (user_id, place_id) VALUES (%s, %s)", (user_id, place_id)
        )
        conn.commit()
        return cursor.lastrowid


def remove_favorite(conn, user_id: int, place_id: int) -> int:
    """Returns how many rows were deleted (0 means it was not a favourite)."""
    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM favorites WHERE user_id = %s AND place_id = %s", (user_id, place_id)
        )
        conn.commit()
        return cursor.rowcount


def list_favorites(conn, user_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT " + PLACE_COLUMNS + PLACE_FROM
            + " JOIN favorites f ON f.place_id = p.place_id"
            + " WHERE f.user_id = %s ORDER BY p.name",
            (user_id,),
        )
        return cursor.fetchall()


def saved_together(conn, place_id: int, limit: int = 5):
    """Market-basket analysis with a SELF-JOIN on favorites.

    f1 and f2 are two aliases of the SAME table. Joining them on the same user_id pairs
    every place a user saved with every OTHER place that user saved. We then keep only the
    pairs where f1 is our place, and count in how many users' lists the pair appears.
    """
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT " + PLACE_COLUMNS + ", COUNT(DISTINCT f1.user_id) AS co_count"
            + """
            FROM favorites f1
            JOIN favorites f2 ON f1.user_id = f2.user_id AND f1.place_id != f2.place_id
            JOIN places p ON f2.place_id = p.place_id
            JOIN cities c ON p.city_id = c.city_id
            JOIN categories cat ON p.category_id = cat.category_id
            WHERE f1.place_id = %s
            GROUP BY p.place_id, p.name, p.avg_cost, p.rating, p.latitude, p.longitude,
                     c.name, cat.name
            ORDER BY co_count DESC, p.name
            LIMIT %s
            """,
            (place_id, limit),
        )
        return cursor.fetchall()
