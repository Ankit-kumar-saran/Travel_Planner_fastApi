"""Raw SQL for reviews."""

REVIEW_SELECT = """
    SELECT r.id, r.user_id, u.name AS user_name, r.place_id, r.rating, r.comment, r.created_at
    FROM reviews r
    JOIN users u ON r.user_id = u.user_id
"""


def get_review_by_user_and_place(conn, user_id: int, place_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            REVIEW_SELECT + " WHERE r.user_id = %s AND r.place_id = %s", (user_id, place_id)
        )
        return cursor.fetchone()


def get_review_by_id(conn, review_id: int):
    with conn.cursor() as cursor:
        cursor.execute(REVIEW_SELECT + " WHERE r.id = %s", (review_id,))
        return cursor.fetchone()


def create_review(conn, user_id: int, place_id: int, rating, comment) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO reviews (user_id, place_id, rating, comment) VALUES (%s, %s, %s, %s)",
            (user_id, place_id, rating, comment),
        )
        conn.commit()
        return cursor.lastrowid


def update_review(conn, review_id: int, rating, comment) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE reviews SET rating = %s, comment = %s, created_at = NOW() WHERE id = %s",
            (rating, comment, review_id),
        )
        conn.commit()


def delete_review(conn, review_id: int) -> None:
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
        conn.commit()


def list_reviews_for_place(conn, place_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            REVIEW_SELECT + " WHERE r.place_id = %s ORDER BY r.created_at DESC, r.id DESC",
            (place_id,),
        )
        return cursor.fetchall()


def review_stats_for_place(conn, place_id: int):
    """COUNT and AVG computed by MySQL. AVG is NULL when there are no reviews."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS review_count, AVG(rating) AS average_rating "
            "FROM reviews WHERE place_id = %s",
            (place_id,),
        )
        return cursor.fetchone()
