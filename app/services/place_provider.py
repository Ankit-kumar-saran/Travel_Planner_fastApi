"""Fetches places for a city from an EXTERNAL API.

- If GOOGLE_PLACES_API_KEY is set  -> Google Places (primary source in the project report)
- If it is empty                   -> OpenStreetMap (Nominatim + Overpass), free, no key

Both functions return a list of dicts:
    {"name", "category", "rating", "avg_cost", "latitude", "longitude"}
where category is one of "Hotel", "Restaurant", "Attraction".

IMPORTANT: this module only talks to the internet. It never touches the database.
"""
import httpx

from app.config import settings

# Our category name -> the type names the two APIs use
GOOGLE_TYPES = {"Hotel": "lodging", "Restaurant": "restaurant", "Attraction": "tourist_attraction"}
OSM_FILTERS = {
    "Hotel": '["tourism"~"hotel|guest_house|hostel"]',
    "Restaurant": '["amenity"="restaurant"]',
    "Attraction": '["tourism"~"attraction|museum|viewpoint"]',
}
# Google returns price_level 0-4. We turn it into a rough cost in rupees for avg_cost.
GOOGLE_PRICE_MAP = {0: 0, 1: 300, 2: 800, 3: 1800, 4: 4000}

HTTP_TIMEOUT = 25.0
# Nominatim's usage policy requires an identifying User-Agent
HEADERS = {"User-Agent": "WanderSync-student-project/1.0"}


class ProviderError(Exception):
    """Raised when the external API fails. The route turns this into a 502 response."""


def fetch_city_places(city_name: str) -> list[dict]:
    try:
        if settings.google_places_api_key:
            return _fetch_google(city_name)
        return _fetch_osm(city_name)
    except httpx.HTTPError as exc:
        raise ProviderError(f"External place API failed: {exc}") from exc


# ---------------- Google Places ----------------

def _fetch_google(city_name: str) -> list[dict]:
    results: list[dict] = []
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        # One text search per category (Places API "Text Search")
        for category, g_type in GOOGLE_TYPES.items():
            response = client.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={
                    "query": f"{g_type.replace('_', ' ')} in {city_name}",
                    "type": g_type,
                    "key": settings.google_places_api_key,
                },
            )
            response.raise_for_status()
            data = response.json()
            if data.get("status") not in ("OK", "ZERO_RESULTS"):
                raise ProviderError(f"Google Places error: {data.get('status')} "
                                    f"{data.get('error_message', '')}")
            for item in data.get("results", []):
                loc = item.get("geometry", {}).get("location", {})
                if "lat" not in loc or "lng" not in loc or not item.get("name"):
                    continue
                results.append({
                    "name": item["name"][:100],
                    "category": category,
                    "rating": item.get("rating"),
                    "avg_cost": GOOGLE_PRICE_MAP.get(item.get("price_level"), 0),
                    "latitude": round(loc["lat"], 6),
                    "longitude": round(loc["lng"], 6),
                })
    return results


# ---------------- OpenStreetMap ----------------

def _fetch_osm(city_name: str) -> list[dict]:
    with httpx.Client(timeout=HTTP_TIMEOUT, headers=HEADERS) as client:
        # 1. Nominatim: city name -> bounding box
        geo = client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city_name, "format": "json", "limit": 1},
        )
        geo.raise_for_status()
        found = geo.json()
        if not found:
            return []                       # unknown city: nothing to cache
        south, north, west, east = (float(x) for x in found[0]["boundingbox"])
        bbox = f"{south},{west},{north},{east}"

        # 2. Overpass: all nodes of each category inside that box (max 40 per category)
        results: list[dict] = []
        for category, tag_filter in OSM_FILTERS.items():
            query = f"[out:json][timeout:20];node{tag_filter}[name]({bbox});out 40;"
            response = client.post("https://overpass-api.de/api/interpreter", data={"data": query})
            response.raise_for_status()
            for node in response.json().get("elements", []):
                name = node.get("tags", {}).get("name")
                if not name:
                    continue
                results.append({
                    "name": name[:100],
                    "category": category,
                    "rating": None,         # OpenStreetMap has no ratings
                    "avg_cost": 0,
                    "latitude": round(node["lat"], 6),
                    "longitude": round(node["lon"], 6),
                })
        return results
