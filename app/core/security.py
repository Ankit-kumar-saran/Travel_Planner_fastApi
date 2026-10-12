import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.config import settings

# bcrypt can only handle passwords up to 72 bytes
MAX_PASSWORD_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Turn a plain password into a salted bcrypt hash (safe to store in the DB)."""
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash or password too long: treat as "does not match"
        return False


def create_access_token(user_id: int, role: str) -> str:
    """Create a signed JWT. `sub` (subject) = who the token belongs to."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Verify the signature and expiry, and return the payload. Raises JWTError if invalid."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def generate_reset_token() -> str:
    """Random one-time token for password reset (this is what we email to the user)."""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """We store only the SHA-256 hash of the reset token, never the token itself."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
