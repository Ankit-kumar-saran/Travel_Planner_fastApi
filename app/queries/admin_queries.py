"""Raw SQL for the admin analytics dashboard."""


def get_totals(conn) -> dict:
    """Platform totals. Each number is a small scalar subquery, all in one round trip."""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM users) AS total_users,
                (SELECT COUNT(DISTINCT city_id) FROM places) AS cached_cities,
                (SELECT COUNT(*) FROM places) AS cached_places
            """
        )
        return cursor.fetchone()


def most_searched_city(conn):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.name, COUNT(*) AS search_count
            FROM user_searches us
            JOIN cities c ON us.city_id = c.city_id
            GROUP BY c.city_id, c.name
            ORDER BY search_count DESC, c.name
            LIMIT 1
            """
        )
        return cursor.fetchone()


def most_saved_place(conn):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.name, COUNT(*) AS save_count
            FROM favorites f
            JOIN places p ON f.place_id = p.place_id
            GROUP BY p.place_id, p.name
            ORDER BY save_count DESC, p.name
            LIMIT 1
            """
        )
        return cursor.fetchone()


def activity_last_7_days(conn):
    """Recursive CTE that builds a calendar of the last 7 days (today - 6 ... today),
    then LEFT JOINs the searches onto it. Quiet days still appear, with 0.

    How the recursion works:
      1. The first SELECT (anchor) produces one row: the date 6 days ago.
      2. The second SELECT (recursive part) reads the previous row and adds one day.
      3. It repeats until the date reaches today (the WHERE stops the loop).
    """
    with conn.cursor() as cursor:
        cursor.execute(
            """
            WITH RECURSIVE date_series AS (
                SELECT CURDATE() - INTERVAL 6 DAY AS activity_day
                UNION ALL
                SELECT activity_day + INTERVAL 1 DAY
                FROM date_series
                WHERE activity_day < CURDATE()
            )
            SELECT ds.activity_day AS day,
                   COUNT(DISTINCT us.user_id) AS active_users,
                   COUNT(us.id) AS searches
            FROM date_series ds
            LEFT JOIN user_searches us
                   ON us.searched_at >= ds.activity_day
                  AND us.searched_at <  ds.activity_day + INTERVAL 1 DAY
            GROUP BY ds.activity_day
            ORDER BY ds.activity_day
            """
        )
        return cursor.fetchall()


def city_stats(conn):
    """Per city: number of places, average cost, and the most common category
    (found with a correlated subquery that runs once per city)."""
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.name AS city,
                   COUNT(p.place_id) AS cached_places,
                   AVG(p.avg_cost) AS avg_cost,
                   (SELECT cat.name
                    FROM places p2
                    JOIN categories cat ON p2.category_id = cat.category_id
                    WHERE p2.city_id = c.city_id
                    GROUP BY cat.category_id, cat.name
                    ORDER BY COUNT(*) DESC, cat.name
                    LIMIT 1) AS top_category
            FROM cities c
            LEFT JOIN places p ON p.city_id = c.city_id
            GROUP BY c.city_id, c.name
            ORDER BY cached_places DESC, c.name
            """
        )
        return cursor.fetchall()
