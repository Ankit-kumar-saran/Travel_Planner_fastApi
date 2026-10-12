from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES


def _check_password_bytes(value: str) -> str:
    # bcrypt ignores/rejects anything past 72 bytes, so we reject it up front
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Password is too long (max 72 bytes)")
    return value


class UserCreate(BaseModel):
    """Body of POST /auth/register"""
    name: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6)

    _check_password = field_validator("password")(_check_password_bytes)


class UserLogin(BaseModel):
    """Body of POST /auth/login"""
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """What we send back about a user. There is NO password field here on purpose."""
    user_id: int
    name: str
    email: str
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6)

    _check_password = field_validator("new_password")(_check_password_bytes)


class MessageOut(BaseModel):
    message: str
