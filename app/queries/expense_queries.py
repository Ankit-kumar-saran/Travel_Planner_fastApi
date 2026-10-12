"""Raw SQL for expenses."""


def add_expense(conn, trip_id: int, amount, category, spent_date, note) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO expenses (trip_id, amount, category, spent_date, note) "
            "VALUES (%s, %s, %s, %s, %s)",
            (trip_id, amount, category, spent_date, note),
        )
        conn.commit()
        return cursor.lastrowid


def get_expense(conn, trip_id: int, expense_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, trip_id, amount, category, spent_date, note FROM expenses "
            "WHERE trip_id = %s AND id = %s",
            (trip_id, expense_id),
        )
        return cursor.fetchone()


def list_expenses(conn, trip_id: int):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, trip_id, amount, category, spent_date, note FROM expenses "
            "WHERE trip_id = %s ORDER BY spent_date DESC, id DESC",
            (trip_id,),
        )
        return cursor.fetchall()


def delete_expense(conn, expense_id: int) -> None:
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
        conn.commit()


def expense_totals_by_category(conn, trip_id: int):
    """GROUP BY example: how much was spent in each category."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE trip_id = %s GROUP BY category ORDER BY total DESC",
            (trip_id,),
        )
        return cursor.fetchall()
