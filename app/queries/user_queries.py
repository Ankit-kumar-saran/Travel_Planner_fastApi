"""Raw SQL for the users and password_resets tables.

Rule used in every query file: values ALWAYS go through %s placeholders and a
parameter tuple (never f-strings), so SQL injection is impossible.
"""


def get_user_by_email(conn, email: str):
    """Used at login. Includes password_hash so we can verify the password."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT user_id, name, email, password_hash, role FROM users WHERE email = %s",
            (email,),
        )
        return cursor.fetchone()


def get_user_by_id(conn, user_id: int):
    """Used on every protected request. No password_hash: we never need it here."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT user_id, name, email, role FROM users WHERE user_id = %s",
            (user_id,),
        )
        return cursor.fetchone()


def create_user(conn, name: str, email: str, password_hash: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
            (name, email, password_hash),
        )
        conn.commit()
        # lastrowid = the auto-increment id of the row we just inserted
        return cursor.lastrowid


# ---------- Password reset ----------

def create_password_reset(conn, user_id: int, token_hash: str) -> None:
    """Store a reset token (hashed). It expires 30 minutes from now (time is taken from MySQL)."""
    with conn.cursor() as cursor:
        # Old unused tokens of this user stop working as soon as a new one is requested
        cursor.execute("UPDATE password_resets SET used = 1 WHERE user_id = %s", (user_id,))
        cursor.execute(
            "INSERT INTO password_resets (user_id, token_hash, expires_at) "
            "VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL 30 MINUTE))",
            (user_id, token_hash),
        )
        conn.commit()


def get_valid_password_reset(conn, token_hash: str):
    """Returns the reset row only if it is unused and not expired."""
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, user_id FROM password_resets "
            "WHERE token_hash = %s AND used = 0 AND expires_at > NOW()",
            (token_hash,),
        )
        return cursor.fetchone()


def apply_password_reset(conn, reset_id: int, user_id: int, new_password_hash: str) -> None:
    """Change the password and burn the token in ONE transaction (both or neither)."""
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE user_id = %s",
            (new_password_hash, user_id),
        )
        cursor.execute("UPDATE password_resets SET used = 1 WHERE id = %s", (reset_id,))
        conn.commit()
