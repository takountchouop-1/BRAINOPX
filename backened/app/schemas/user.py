from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UserLogin(BaseModel):
    """What the client sends when logging in."""
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserCreate(BaseModel):
    """What the client sends when registering a new user."""
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)


class UserUpdate(BaseModel):
    """What the client sends when updating their profile."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    email: Optional[EmailStr] = None


class UserResponse(BaseModel):
    """
    What the API sends back — never includes the password or its hash.

    `role` is included here (not just on UserAdminResponse) because
    this is what /auth/login, /auth/register and /auth/me return: a
    user needs to see their own role so the frontend can hide actions
    they are not allowed to take. It is not sensitive information —
    it is who they themselves are.
    """
    id: int
    full_name: str
    email: EmailStr
    profile_picture: Optional[str] = None
    is_active: bool
    role: str = "member"

    class Config:
        from_attributes = True


class UserAdminResponse(UserResponse):
    """
    A user as shown on the User Management page.

    Only ever returned to an admin — see get_current_admin_user.
    """
    role: str
    access: list[str] = []
    address: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None


class UserCreateByAdmin(BaseModel):
    """
    What an admin sends to create a new user.

    No password field: one is generated server-side so an admin never
    has to know — or choose — another person's password. It is
    returned once in the response and emailed if SMTP is configured.
    """
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    address: Optional[str] = Field(None, max_length=255)
    role: str = Field("member")
    access: list[str] = Field(default_factory=list)


class UserAdminUpdate(BaseModel):
    """What an admin sends to change an existing user's access."""
    role: Optional[str] = None
    access: Optional[list[str]] = None
    address: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class TokenResponse(BaseModel):
    """What the API sends back after a successful login."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Password reset flow ---

class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetVerify(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class PasswordResetConfirm(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6, max_length=100)
