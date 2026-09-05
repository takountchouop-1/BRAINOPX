import os
import random
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
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

RESET_CODE_VALID_MINUTES = 5

# --- Google OAuth (Sign in with Google) ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"


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


# --- Sign in with Google ---

@router.get("/google/login")
def google_login():
    """
    Kicks off the Google OAuth flow: sends the browser to Google's own
    account chooser / consent screen. Google redirects back to
    /api/auth/google/callback once the user picks an account.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured on the server.",
        )

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        # Always show the account chooser instead of silently
        # reusing whichever Google session is already active.
        "prompt": "select_account",
        "access_type": "online",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}")


@router.get("/google/callback")
def google_callback(code: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    """
    Google lands the browser back here with either an authorization
    `code` or an `error` (e.g. the user clicked Cancel). Exchanges the
    code for tokens, looks up the Google profile, finds-or-creates the
    matching local user, then hands off to the frontend with a normal
    BRAINOPX access token so the rest of the app doesn't need to know
    the user signed in via Google.
    """
    if error or not code:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_auth_failed")

    token_resp = requests.post(
        GOOGLE_TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if not token_resp.ok:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_auth_failed")

    google_access_token = token_resp.json().get("access_token")

    userinfo_resp = requests.get(
        GOOGLE_USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {google_access_token}"},
        timeout=10,
    )
    if not userinfo_resp.ok:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_auth_failed")

    profile = userinfo_resp.json()
    email = profile.get("email")
    if not email:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_auth_failed")

    user = db.query(User).filter(User.email == email).first()

    if user:
        if not user.profile_picture and profile.get("picture"):
            user.profile_picture = profile["picture"]
    else:
        user = User(
            full_name=profile.get("name") or email.split("@")[0],
            email=email,
            # Google-created accounts never sign in with a password;
            # this hash is unusable for that purpose (random, discarded).
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            profile_picture=profile.get("picture"),
        )
        db.add(user)

    if not user.is_active:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=account_deactivated")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, email=user.email)
    return RedirectResponse(f"{FRONTEND_URL}/auth/google/callback?token={token}")