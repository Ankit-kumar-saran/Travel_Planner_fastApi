from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
    rating: Decimal = Field(ge=0, le=5, max_digits=2, decimal_places=1)
    comment: str | None = Field(default=None, max_length=2000)


class ReviewOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    place_id: int
    rating: float | None = None
    comment: str | None = None
    created_at: datetime | None = None


class ReviewListOut(BaseModel):
    place_id: int
    review_count: int
    average_rating: float | None = None
    reviews: list[ReviewOut]
