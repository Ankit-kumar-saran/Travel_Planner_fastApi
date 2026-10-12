from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.database import get_db
from app.queries import place_queries as pq
from app.queries import review_queries as rq
from app.schemas.review import ReviewCreate, ReviewListOut, ReviewOut

router = APIRouter(tags=["reviews"])


def _place_or_404(conn, place_id: int):
    if pq.get_place_by_id(conn, place_id) is None:
        raise HTTPException(status_code=404, detail="Place not found")


@router.get("/places/{place_id}/reviews", response_model=ReviewListOut)
def list_reviews(place_id: int, conn=Depends(get_db)):
    _place_or_404(conn, place_id)
    stats = rq.review_stats_for_place(conn, place_id)
    return ReviewListOut(
        place_id=place_id,
        review_count=stats["review_count"],
        average_rating=stats["average_rating"],
        reviews=rq.list_reviews_for_place(conn, place_id),
    )


@router.post("/places/{place_id}/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def add_review(place_id: int, body: ReviewCreate, conn=Depends(get_db),
               user: dict = Depends(get_current_user)):
    _place_or_404(conn, place_id)
    if rq.get_review_by_user_and_place(conn, user["user_id"], place_id):
        raise HTTPException(status_code=400, detail="You already reviewed this place. Edit it instead.")
    new_id = rq.create_review(conn, user["user_id"], place_id, body.rating, body.comment)
    return rq.get_review_by_id(conn, new_id)


@router.put("/reviews/{review_id}", response_model=ReviewOut)
def edit_review(review_id: int, body: ReviewCreate, conn=Depends(get_db),
                user: dict = Depends(get_current_user)):
    review = rq.get_review_by_id(conn, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    if review["user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="You can only edit your own review")
    rq.update_review(conn, review_id, body.rating, body.comment)
    return rq.get_review_by_id(conn, review_id)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_review(review_id: int, conn=Depends(get_db), user: dict = Depends(get_current_user)):
    review = rq.get_review_by_id(conn, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    # Owner can delete their own review; an admin can delete any (moderation)
    if review["user_id"] != user["user_id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="You can only delete your own review")
    rq.delete_review(conn, review_id)
