from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, auth, expenses, favorites, places, reviews, trips, users

app = FastAPI(
    title="WanderSync API",
    description="Smart travel planner: city search with MySQL cache, trips, favourites, expenses.",
    version="1.0.0",
)

# CORS: lets the browser frontend (a different origin/port) call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(places.router)
app.include_router(favorites.router)
app.include_router(reviews.router)
app.include_router(trips.router)
app.include_router(expenses.router)
app.include_router(admin.router)


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "app": "WanderSync API"}
