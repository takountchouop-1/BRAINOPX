import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import User
from ..db.deps import get_current_user
from ..schemas.user import (
    UserCreate,
    UserResponse,
    UserLogin,
    TokenResponse,
    PasswordResetRequest,
    PasswordResetVerify,
    PasswordResetConfirm,
)
from ..core.security import hash_password, verify_password
from ..core.email_service import send_password_reset_email
from ..core.jwt_service import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

RESET_CODE_VALID_MINUTES = 15


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    hashed_pw = hash_password(user_in.password)

    new_user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        hashed_password=hashed_pw,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=TokenResponse)
def login_user(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()

    invalid_credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )

    if not user:
        raise invalid_credentials_error

    if not verify_password(credentials.password, user.hashed_password):
        raise invalid_credentials_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, email=user.email)

    return TokenResponse(access_token=token, user=user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Example protected route: returns whoever the token belongs to."""
    return current_user


# --- Step 1: request a reset code ---
@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    generic_message = {"message": "If this email is registered, a reset code has been sent."}

    if not user:
        return generic_message

    code = f"{random.randint(0, 999999):06d}"
    user.reset_code = code
    user.reset_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=RESET_CODE_VALID_MINUTES)
    db.commit()

    send_password_reset_email(user.email, code)

    return generic_message


# --- Step 2: verify the code (without changing anything yet) ---
@router.post("/verify-reset-code", status_code=status.HTTP_200_OK)
def verify_reset_code(payload: PasswordResetVerify, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    invalid_code_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset code.",
    )

    if not user or not user.reset_code or not user.reset_code_expires_at:
        raise invalid_code_error

    if user.reset_code != payload.code:
        raise invalid_code_error

    expires_at = user.reset_code_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        raise invalid_code_error

    return {"message": "Code verified. You may now set a new password."}


# --- Step 3: set the new password ---
@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    invalid_code_error = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset code.",
    )

    if not user or not user.reset_code or not user.reset_code_expires_at:
        raise invalid_code_error

    if user.reset_code != payload.code:
        raise invalid_code_error

    expires_at = user.reset_code_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expires_at:
        raise invalid_code_error

    user.hashed_password = hash_password(payload.new_password)
    user.reset_code = None
    user.reset_code_expires_at = None
    db.commit()

    return {"message": "Password has been reset successfully. You can now sign in."}