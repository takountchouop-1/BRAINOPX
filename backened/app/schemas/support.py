from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SupportTicketCreate(BaseModel):
    """What a user sends to open a new support thread."""

    subject: str = Field(..., min_length=1, max_length=200)
    body: Optional[str] = None
    request_id: Optional[int] = None


class SupportMessageCreate(BaseModel):
    """A single message sent into an existing thread."""

    body: str = Field(..., min_length=1)


class SupportMessageOut(BaseModel):
    id: int
    ticket_id: int
    sender_id: int
    sender_role: str
    body: str
    read_by_user: bool
    read_by_specialist: bool
    created_at: datetime
    sender_name: Optional[str] = None

    class Config:
        from_attributes = True


class SupportTicketOut(BaseModel):
    """A ticket as listed in an inbox — with the bits each side needs."""

    id: int
    user_id: int
    request_id: Optional[int] = None
    subject: str
    status: str
    claimed_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    user_name: Optional[str] = None
    user_email: Optional[str] = None
    unread_count: int = 0
    last_message_at: Optional[datetime] = None
    last_message_preview: Optional[str] = None


class SupportTicketDetail(BaseModel):
    """A single ticket opened in full, with its whole thread."""

    ticket: SupportTicketOut
    messages: list[SupportMessageOut]
