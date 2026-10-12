from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymysql.err import IntegrityError

from app.core.dependencies import get_optional_user, require_admin
from app.database import get_db
from app.queries import favorite_queries as fq
from app.queries import place_queries as q
from app.schemas.place import (
    CityPlacesOut,
    NameCreate,
    NameOut,
    PlaceCreate,
    PlaceOut,
    RecommendationOut,
)
from app.services.city_cache import get_places_with_cache

router = APIRouter(tags=["places"])

SortKey = Literal["rating", "cost", "name", "distance"]


# ---------- Cities ----------

@router.get("/cities", response_model=list[NameOut])
def list_cities(conn=Depends(get_db)):
    return q.get_all_cities(conn)


@router.post("/cities", response_model=NameOut, status_code=status.HTTP_201_CREATED)
def add_city(body: NameCreate, conn=Depends(get_db), admin: dict = Depends(require_admin)):
    try:
        new_id = q.create_city(conn, body.name)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="City already exists")
    return {"id": new_id, "name": body.name}


@router.get("/cities/{city_name}/places", response_model=CityPlacesOut)
def city_places(
    city_name: str,
    category: str | None = Query(default=None, description="Hotel, Restaurant or Attraction"),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    sort: SortKey = "rating",
    ref_lat: float | None = Query(default=None, ge=-90, le=90),
    ref_lng: float | None = Query(default=None, ge=-180, le=180),
    max_distance_km: float | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    conn=Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    """THE cache-aside endpoint: served from MySQL, or fetched from the API once and saved."""
    if (ref_lat is None) != (ref_lng is None):
        raise HTTPException(status_code=422, detail="Send both ref_lat and ref_lng, or neither")
    if sort == "distance" and ref_lat is None:
        raise HTTPException(status_code=422, detail="sort=distance needs ref_lat and ref_lng")

    city_name = city_name.strip()
    filters = dict(
        category_name=category, min_rating=min_rating, sort=sort, ref_lat=ref_lat,
        ref_lng=ref_lng, max_distance_km=max_distance_km, limit=limit, offset=offset,
    )
    source, city_id, places = get_places_with_cache(conn, city_name, filters)
    # Log the search (user_id is None for visitors). This feeds the admin analytics.
    q.log_search(conn, user["user_id"] if user else None, city_id)
    return CityPlacesOut(city=city_name, source=source, count=len(places), places=places)


# ---------- Categories ----------

@router.get("/categories", response_model=list[NameOut])
def list_categories(conn=Depends(get_db)):
    return q.get_all_categories(conn)


@router.post("/categories", response_model=NameOut, status_code=status.HTTP_201_CREATED)
def add_category(body: NameCreate, conn=Depends(get_db), admin: dict = Depends(require_admin)):
    try:
        new_id = q.create_category(conn, body.name)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Category already exists")
    return {"id": new_id, "name": body.name}


# ---------- Places ----------

@router.get("/places", response_model=list[PlaceOut])
def list_places(
    city_id: int | None = None,
    category_id: int | None = None,
    min_rating: float | None = Query(default=None, ge=0, le=5),
    q_text: str | None = Query(default=None, alias="q", max_length=100),
    sort: Literal["rating", "cost", "name"] = "rating",
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    conn=Depends(get_db),
):
    return q.search_places(
        conn, city_id=city_id, category_id=category_id, min_rating=min_rating,
        q=q_text, sort=sort, limit=limit, offset=offset,
    )


@router.get("/places/nearby", response_model=list[PlaceOut])
def nearby_places(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=5, gt=0, le=500),
    category_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    conn=Depends(get_db),
):
    """Places within `radius_km` of a point, nearest first (Haversine formula in SQL)."""
    return q.search_places(
        conn, category_id=category_id, ref_lat=lat, ref_lng=lng,
        max_distance_km=radius_km, sort="distance", limit=limit,
    )


@router.get("/places/best-value", response_model=list[PlaceOut])
def best_value(
    city_id: int,
    max_cost: float = Query(gt=0),
    conn=Depends(get_db),
):
    """Calls the MySQL stored procedure GetBestValuePlaces (see sql/procedures.sql)."""
    return q.best_value_places(conn, city_id, max_cost)


@router.get("/places/{place_id}", response_model=PlaceOut)
def read_place(place_id: int, conn=Depends(get_db)):
    place = q.get_place_by_id(conn, place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    return place


@router.post("/places", response_model=PlaceOut, status_code=status.HTTP_201_CREATED)
def add_place(body: PlaceCreate, conn=Depends(get_db), admin: dict = Depends(require_admin)):
    try:
        new_id = q.create_place(conn, body)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Invalid city_id or category_id")
    return q.get_place_by_id(conn, new_id)


@router.get("/places/{place_id}/recommendations", response_model=RecommendationOut)
def recommendations(place_id: int, conn=Depends(get_db)):
    """'Frequently saved together': other places saved by users who saved this one."""
    if q.get_place_by_id(conn, place_id) is None:
        raise HTTPException(status_code=404, detail="Place not found")
    rows = fq.saved_together(conn, place_id)
    message = None if rows else "Not enough favorite history yet"
    return RecommendationOut(place_id=place_id, message=message, recommendations=rows)
