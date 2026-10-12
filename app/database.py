import pymysql
# By default pymysql returns each row as a tuple. DictCursor returns a dict instead,
# so we can write row["name"] instead of row[1].
from pymysql.cursors import DictCursor

from app.config import settings


def get_connection():
    """Open a NEW MySQL connection. The caller must close it."""
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=DictCursor,
        # We control transactions ourselves with conn.commit() / conn.rollback()
        autocommit=False,
    )


def get_db():
    """FastAPI dependency: gives one connection per request and always cleans up.

    Usage in a route:   def my_route(conn = Depends(get_db)): ...

    Code before `yield` runs before the route. Code after `yield` runs after the route
    finishes (or fails). This is how FastAPI does "setup and teardown".
    """
    conn = get_connection()
    try:
        yield conn
    except Exception:
        # Something failed in the route: undo any half-finished changes
        conn.rollback()
        raise
    finally:
        conn.close()
