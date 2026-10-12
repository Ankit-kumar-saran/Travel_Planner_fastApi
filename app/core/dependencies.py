from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import decode_access_token
from app.database import get_db
from app.queries.user_queries import get_user_by_id

# Reads the "Authorization: Bearer <token>" header.
# auto_error=False means: if the header is missing, do NOT fail here, give us None.
# We decide ourselves whether a missing token is an error (see the two functions below).
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    conn=Depends(get_db),
) -> dict:
    """Use on routes that REQUIRE login. Returns {user_id, name, email, role}."""
    if credentials is None:
        raise _unauthorized()
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise _unauthorized()

    # We re-read the user (and the role) from the database on every request,
    # so a deleted user or a changed role takes effect immediately.
    user = get_user_by_id(conn, user_id)
    if user is None:
        raise _unauthorized()
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    conn=Depends(get_db),
) -> dict | None:
    """Use on public routes that behave a little differently for logged-in users.
    Returns the user, or None if there is no (valid) token."""
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        return get_user_by_id(conn, int(payload.get("sub")))
    except (JWTError, TypeError, ValueError):
        return None


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Use on admin-only routes. Logged-in AND role == 'admin', otherwise 403."""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
