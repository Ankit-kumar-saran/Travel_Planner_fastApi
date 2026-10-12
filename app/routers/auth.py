from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pymysql.err import IntegrityError

from app.core.security import (
    create_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.database import get_db
from app.queries import user_queries as uq
from app.schemas.user import (
    ForgotPasswordRequest,
    MessageOut,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserLogin,
    UserOut,
)
from app.services.email_service import send_reset_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, conn=Depends(get_db)):
    if uq.get_user_by_email(conn, body.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    try:
        new_id = uq.create_user(conn, body.name, body.email, hash_password(body.password))
    except IntegrityError:
        # Two people registering the same email at the same instant: the UNIQUE key catches it
        raise HTTPException(status_code=400, detail="Email already registered")
    return uq.get_user_by_id(conn, new_id)


@router.post("/login", response_model=Token)
def login(body: UserLogin, conn=Depends(get_db)):
    user = uq.get_user_by_email(conn, body.email)
    # Same message for "no such email" and "wrong password": do not reveal which emails exist
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["user_id"], user["role"])
    return Token(access_token=token, role=user["role"])


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(body: ForgotPasswordRequest, background: BackgroundTasks, conn=Depends(get_db)):
    user = uq.get_user_by_email(conn, body.email)
    if user:
        token = generate_reset_token()
        uq.create_password_reset(conn, user["user_id"], hash_reset_token(token))
        # BackgroundTasks sends the email AFTER the response, so the user does not wait
        background.add_task(send_reset_email, user["email"], token)
    # Always the same answer, so nobody can use this endpoint to find out who is registered
    return MessageOut(message="If that email is registered, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageOut)
def reset_password(body: ResetPasswordRequest, conn=Depends(get_db)):
    reset = uq.get_valid_password_reset(conn, hash_reset_token(body.token))
    if reset is None:
        raise HTTPException(status_code=400, detail="Reset token is invalid or has expired")
    uq.apply_password_reset(conn, reset["id"], reset["user_id"], hash_password(body.new_password))
    return MessageOut(message="Password updated. You can log in now.")
