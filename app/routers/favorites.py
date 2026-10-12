from fastapi import APIRouter, Depends, HTTPException, status
from pymysql.err import IntegrityError

from app.core.dependencies import get_current_user
from app.database import get_db
from app.queries import favorite_queries as fq
from app.queries import place_queries as pq
from app.schemas.favorite import FavoriteCreate
from app.schemas.place import PlaceOut

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=list[PlaceOut])
def my_favorites(conn=Depends(get_db), user: dict = Depends(get_current_user)):
    return fq.list_favorites(conn, user["user_id"])


@router.post("", response_model=PlaceOut, status_code=status.HTTP_201_CREATED)
def save_favorite(body: FavoriteCreate, conn=Depends(get_db), user: dict = Depends(get_current_user)):
    place = pq.get_place_by_id(conn, body.place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    if fq.get_favorite(conn, user["user_id"], body.place_id):
        raise HTTPException(status_code=400, detail="Already in favorites")
    try:
        fq.add_favorite(conn, user["user_id"], body.place_id)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Could not save favorite")
    return place


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(place_id: int, conn=Depends(get_db), user: dict = Depends(get_current_user)):
    if fq.remove_favorite(conn, user["user_id"], place_id) == 0:
        raise HTTPException(status_code=404, detail="Not in your favorites")
