from pydantic import BaseModel


class FavoriteCreate(BaseModel):
    place_id: int
