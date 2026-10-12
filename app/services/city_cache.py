"""The cache-aside flow with MySQL advisory locks (the heart of the project).

    1. Look in MySQL.                         -> found? return it  (cache HIT)
    2. Not found: GET_LOCK('city_lock_<name>')  (only ONE request per city gets past)
    3. Look in MySQL AGAIN                    (another request may have filled it while we waited)
    4. Still empty: call the external API, save the places, commit.
    5. RELEASE_LOCK, return the places.       (always, even if something failed)
"""
import hashlib

from fastapi import HTTPException

from app.queries import place_queries as q
from app.services import place_provider

LOCK_TIMEOUT_SECONDS = 30


def _lock_name(city_name: str) -> str:
    # MySQL lock names are limited to 64 characters, so we hash long/odd city names
    digest = hashlib.sha1(city_name.lower().encode("utf-8")).hexdigest()[:20]
    return f"wandersync_city_{digest}"


def get_places_with_cache(conn, city_name: str, search_kwargs: dict) -> tuple[str, int | None, list]:
    """Returns (source, city_id, places).
    `source` is "cache" when MySQL already had the city, or "api" when we just fetched it.
    `search_kwargs` are the filters passed to place_queries.search_places."""

    # ---- Step 1: try the cache ----
    city = q.get_city_by_name(conn, city_name)
    if city and q.count_places_in_city(conn, city["city_id"]) > 0:
        places = q.search_places(conn, city_id=city["city_id"], **search_kwargs)
        return "cache", city["city_id"], places

    # ---- Step 2: cache miss -> take the lock for this city ----
    lock = _lock_name(city_name)
    if not q.acquire_lock(conn, lock, LOCK_TIMEOUT_SECONDS):
        raise HTTPException(status_code=503, detail="City is being loaded by another request, please retry")

    source = "cache"
    try:
        # IMPORTANT: end the current transaction before re-checking.
        # InnoDB's default isolation (REPEATABLE READ) shows each transaction a snapshot taken
        # at its FIRST read. Our Step-1 read already created that snapshot, so without this
        # commit the re-check below would still see the OLD empty cache and call the API again,
        # even though another request has just filled it. A fresh transaction = fresh snapshot.
        conn.commit()

        # ---- Step 3: re-check (we may have waited while someone else filled the cache) ----
        city = q.get_city_by_name(conn, city_name)
        if not (city and q.count_places_in_city(conn, city["city_id"]) > 0):
            # ---- Step 4: really empty -> call the external API (once!) ----
            try:
                items = place_provider.fetch_city_places(city_name)
            except place_provider.ProviderError as exc:
                raise HTTPException(status_code=502, detail=str(exc))
            if not items:
                raise HTTPException(status_code=404, detail=f"No places found for '{city_name}'")

            city_id = q.get_or_create_city(conn, city_name)
            category_ids = q.get_category_ids_by_name(conn)
            for item in items:
                category_id = category_ids.get(item["category"].lower())
                if category_id is not None:
                    q.insert_place_if_new(conn, city_id, category_id, item)
            conn.commit()           # all places of the city are saved together, or none
            source = "api"
            city = q.get_city_by_name(conn, city_name)

        places = q.search_places(conn, city_id=city["city_id"], **search_kwargs)
        return source, city["city_id"], places
    except Exception:
        conn.rollback()
        raise
    finally:
        # ---- Step 5: always release, even on error ----
        q.release_lock(conn, lock)
