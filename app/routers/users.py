from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: dict = Depends(get_current_user)):
    return current_user
