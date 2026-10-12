from decimal import Decimal

from pydantic import BaseModel, Field


# ---------- Cities and categories ----------

class NameCreate(BaseModel):
    """Body for creating a city or a category"""
    name: str = Field(min_length=2, max_length=50)


class NameOut(BaseModel):
    id: int
    name: str


# ---------- Places ----------

class PlaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    avg_cost: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=10, decimal_places=2)
    rating: Decimal | None = Field(default=None, ge=0, le=5, max_digits=2, decimal_places=1)
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    city_id: int
    category_id: int


class PlaceOut(BaseModel):
    # MySQL DECIMAL values arrive as Decimal objects. We declare them as float here
    # so that the JSON contains real numbers (4.5) instead of strings ("4.5").
    place_id: int
    name: str
    avg_cost: float | None = None
    rating: float | None = None
    latitude: float
    longitude: float
    city: str
    category: str
    # Only filled when the query computed a distance (Haversine) or a value score
    distance_km: float | None = None
    value_score: float | None = None
    # Only filled by the "frequently saved together" query: how many users saved both places
    co_count: int | None = None


class CityPlacesOut(BaseModel):
    """Response of GET /cities/{name}/places"""
    city: str
    # "cache"    = served from MySQL
    # "api"      = fetched from the external API just now (and saved)
    # "database" = same as cache, but the city had been added manually
    source: str
    count: int
    places: list[PlaceOut]


class RecommendationOut(BaseModel):
    """Response of GET /places/{id}/recommendations ("Frequently saved together")"""
    place_id: int
    message: str | None = None
    recommendations: list[PlaceOut]
