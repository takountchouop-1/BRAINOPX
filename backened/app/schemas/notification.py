from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class NotificationCreate(BaseModel):
    """Used internally by the notification service to create a notification."""
    title: str = Field(..., min_length=1, max_length=200)
    message: Optional[str] = None
    type: str = Field("info", pattern=r"^(info|success|warning|error)$")
    link: Optional[str] = None


class NotificationResponse(BaseModel):
    """What the API returns to the frontend."""
    id: int
    user_id: int
    title: str
    message: Optional[str] = None
    type: str
    link: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseModel):
    """Unread notification count."""
    count: int

