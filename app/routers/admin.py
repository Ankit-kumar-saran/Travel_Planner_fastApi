from fastapi import APIRouter, Depends

from app.core.dependencies import require_admin
from app.database import get_db
from app.queries import admin_queries as aq

# Every route here is admin-only: the dependency is applied to the whole router
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/overview")
def overview(conn=Depends(get_db)):
    totals = aq.get_totals(conn)
    city = aq.most_searched_city(conn)
    place = aq.most_saved_place(conn)
    return {
        "total_users": totals["total_users"],
        "cached_cities": totals["cached_cities"],
        "cached_places": totals["cached_places"],
        "most_searched_city": city,      # None if nobody has searched yet
        "most_saved_place": place,       # None if nobody has saved a favourite yet
    }


@router.get("/activity-7d")
def activity_7d(conn=Depends(get_db)):
    """Always exactly 7 rows, even for days with no activity (recursive CTE)."""
    rows = aq.activity_last_7_days(conn)
    return [
        {"day": r["day"].isoformat(), "active_users": r["active_users"], "searches": r["searches"]}
        for r in rows
    ]


@router.get("/city-stats")
def city_stats(conn=Depends(get_db)):
    rows = aq.city_stats(conn)
    return [
        {
            "city": r["city"],
            "cached_places": r["cached_places"],
            "avg_cost": round(float(r["avg_cost"]), 2) if r["avg_cost"] is not None else None,
            "top_category": r["top_category"],
        }
        for r in rows
    ]
