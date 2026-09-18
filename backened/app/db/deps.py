from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError

from .database import get_db
from .models import User
from ..core.jwt_service import decode_access_token

# Simple "paste your token" scheme for Swagger — shows one text field,
# no separate username/password OAuth2 form.
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency to protect routes. Extracts and verifies the JWT from the
    Authorization header, then loads the matching user from the database.
    """
    token = credentials.credentials  # the raw token string, "Bearer " prefix already stripped

    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    return user


def get_current_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency for admin-only routes: user management, granting
    access, deactivating accounts.
    """

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires an administrator account.",
        )

    return current_user


def get_current_specialist_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency for the specialist interface. Admins count too — an
    administrator is a super-set of a specialist — but a plain member
    is refused.
    """

    if current_user.role not in ("specialist", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires a specialist account.",
        )

    return current_user