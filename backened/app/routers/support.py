"""
support.py

Two-sided support threads between users and specialists.

One router, two audiences:

  /api/support/tickets...          — a user's own threads (any signed-in user)
  /api/support/specialist/...      — the specialist shared inbox (specialist or admin)

A ticket owns a thread of SupportMessage rows. Each side keeps its own
read flag on every message, so "unread" is always computed for whoever
is looking, not stored as one shared boolean.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import SupportMessage, SupportTicket, User
from ..db.deps import get_current_user, get_current_specialist_user
from ..schemas.support import (
    SupportMessageCreate,
    SupportMessageOut,
    SupportTicketCreate,
    SupportTicketDetail,
    SupportTicketOut,
)
from ..services.notification_service import create_notification

router = APIRouter(prefix="/api/support", tags=["support"])

TICKET_OPEN = "open"
TICKET_CLAIMED = "claimed"
TICKET_RESOLVED = "resolved"
TICKET_STATUSES = (TICKET_OPEN, TICKET_CLAIMED, TICKET_RESOLVED)

SENDER_USER = "user"
SENDER_SPECIALIST = "specialist"


# ============================================================
# HELPERS
# ============================================================

def _user_lookup(db: Session) -> dict[int, User]:
    """Users referenced by the tickets/messages in a response, cached
    per request so a long thread doesn't re-query the same row."""
    return {u.id: u for u in db.query(User).all()}


def _message_payload(message: SupportMessage, users: dict[int, User]) -> SupportMessageOut:
    sender = users.get(message.sender_id)
    return SupportMessageOut(
        id=message.id,
        ticket_id=message.ticket_id,
        sender_id=message.sender_id,
        sender_role=message.sender_role,
        body=message.body,
        read_by_user=message.read_by_user,
        read_by_specialist=message.read_by_specialist,
        created_at=message.created_at,
        sender_name=sender.full_name if sender else None,
    )


def _unread_count(ticket_id: int, viewer: str, db: Session) -> int:
    if viewer == SENDER_SPECIALIST:
        # Specialist hasn't seen messages the user wrote.
        return (
            db.query(SupportMessage)
            .filter(
                SupportMessage.ticket_id == ticket_id,
                SupportMessage.sender_role == SENDER_USER,
                SupportMessage.read_by_specialist == False,  # noqa: E712
            )
            .count()
        )
    # User hasn't seen messages the specialist wrote.
    return (
        db.query(SupportMessage)
        .filter(
            SupportMessage.ticket_id == ticket_id,
            SupportMessage.sender_role == SENDER_SPECIALIST,
            SupportMessage.read_by_user == False,  # noqa: E712
        )
        .count()
    )


def _ticket_payload(
    ticket: SupportTicket,
    viewer: str,
    db: Session,
    users: dict[int, User],
) -> SupportTicketOut:
    owner = users.get(ticket.user_id)

    last_message = (
        db.query(SupportMessage)
        .filter(SupportMessage.ticket_id == ticket.id)
        .order_by(SupportMessage.id.desc())
        .first()
    )

    preview = None
    if last_message:
        body = (last_message.body or "").strip().replace("\n", " ")
        preview = body[:120] + ("..." if len(body) > 120 else "")

    return SupportTicketOut(
        id=ticket.id,
        user_id=ticket.user_id,
        request_id=ticket.request_id,
        subject=ticket.subject,
        status=ticket.status,
        claimed_by=ticket.claimed_by,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        user_name=owner.full_name if owner else None,
        user_email=owner.email if owner else None,
        unread_count=_unread_count(ticket.id, viewer, db),
        last_message_at=last_message.created_at if last_message else None,
        last_message_preview=preview,
    )


def _get_ticket_for_user(ticket_id: int, user: User, db: Session) -> SupportTicket:
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    if ticket.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ticket.")
    return ticket


def _get_any_ticket(ticket_id: int, db: Session) -> SupportTicket:
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found.")
    return ticket


# ============================================================
# USER SIDE
# ============================================================

@router.get("/tickets", response_model=list[SupportTicketOut])
def list_my_tickets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Every support thread the signed-in user has opened, newest first."""
    tickets = (
        db.query(SupportTicket)
        .filter(SupportTicket.user_id == current_user.id)
        .order_by(SupportTicket.updated_at.desc())
        .all()
    )
    users = _user_lookup(db)
    return [_ticket_payload(t, SENDER_USER, db, users) for t in tickets]


@router.post("/tickets", response_model=SupportTicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    body: SupportTicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Open a new support thread."""
    ticket = SupportTicket(
        user_id=current_user.id,
        request_id=body.request_id,
        subject=body.subject.strip(),
        status=TICKET_OPEN,
    )
    db.add(ticket)
    db.flush()

    if body.body and body.body.strip():
        db.add(SupportMessage(
            ticket_id=ticket.id,
            sender_id=current_user.id,
            sender_role=SENDER_USER,
            body=body.body.strip(),
            read_by_user=True,
            read_by_specialist=False,
        ))

    db.commit()
    db.refresh(ticket)
    users = _user_lookup(db)
    return _ticket_payload(ticket, SENDER_USER, db, users)


@router.get("/tickets/{ticket_id}", response_model=SupportTicketDetail)
def get_my_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One of the user's own threads, with the full message list."""
    ticket = _get_ticket_for_user(ticket_id, current_user, db)

    messages = (
        db.query(SupportMessage)
        .filter(SupportMessage.ticket_id == ticket.id)
        .order_by(SupportMessage.id.asc())
        .all()
    )

    # Opening the thread marks the specialist's messages as read.
    unseen = [
        m for m in messages
        if m.sender_role == SENDER_SPECIALIST and not m.read_by_user
    ]
    if unseen:
        for m in unseen:
            m.read_by_user = True
        db.commit()

    users = _user_lookup(db)
    return SupportTicketDetail(
        ticket=_ticket_payload(ticket, SENDER_USER, db, users),
        messages=[_message_payload(m, users) for m in messages],
    )


@router.post("/tickets/{ticket_id}/messages", response_model=SupportMessageOut, status_code=status.HTTP_201_CREATED)
def send_user_message(
    ticket_id: int,
    body: SupportMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """A user replies in their own thread."""
    ticket = _get_ticket_for_user(ticket_id, current_user, db)

    message = SupportMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        sender_role=SENDER_USER,
        body=body.body.strip(),
        read_by_user=True,
        read_by_specialist=False,
    )
    db.add(message)

    # A user replying to a resolved ticket reopens the conversation.
    if ticket.status == TICKET_RESOLVED:
        ticket.status = TICKET_OPEN
        ticket.resolved_by = None
        ticket.resolved_at = None

    # Explicitly advance the ticket so the specialist inbox re-sorts on
    # the new activity even though the message lives in its own table.
    ticket.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(message)

    users = _user_lookup(db)
    return _message_payload(message, users)


# ============================================================
# SPECIALIST SIDE
# ============================================================

@router.get("/specialist/tickets", response_model=list[SupportTicketOut])
def list_specialist_tickets(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_specialist_user),
):
    """The shared specialist inbox, newest activity first."""
    query = db.query(SupportTicket)

    if status_filter:
        if status_filter not in TICKET_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status must be one of: {', '.join(TICKET_STATUSES)}.",
            )
        query = query.filter(SupportTicket.status == status_filter)

    tickets = query.order_by(SupportTicket.updated_at.desc()).all()
    users = _user_lookup(db)
    return [_ticket_payload(t, SENDER_SPECIALIST, db, users) for t in tickets]


@router.get("/specialist/tickets/{ticket_id}", response_model=SupportTicketDetail)
def get_specialist_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_specialist_user),
):
    """One ticket in full, marking the user's messages as read."""
    ticket = _get_any_ticket(ticket_id, db)

    messages = (
        db.query(SupportMessage)
        .filter(SupportMessage.ticket_id == ticket.id)
        .order_by(SupportMessage.id.asc())
        .all()
    )

    unseen = [
        m for m in messages
        if m.sender_role == SENDER_USER and not m.read_by_specialist
    ]
    if unseen:
        for m in unseen:
            m.read_by_specialist = True
        db.commit()

    users = _user_lookup(db)
    return SupportTicketDetail(
        ticket=_ticket_payload(ticket, SENDER_SPECIALIST, db, users),
        messages=[_message_payload(m, users) for m in messages],
    )


@router.post("/specialist/tickets/{ticket_id}/messages", response_model=SupportMessageOut, status_code=status.HTTP_201_CREATED)
def send_specialist_message(
    ticket_id: int,
    body: SupportMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_specialist_user),
):
    """A specialist replies; the ticket's user gets an in-app notification."""
    ticket = _get_any_ticket(ticket_id, db)

    message = SupportMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        sender_role=SENDER_SPECIALIST,
        body=body.body.strip(),
        read_by_user=False,
        read_by_specialist=True,
    )
    db.add(message)

    # Replying claims the ticket if nobody has it yet.
    if ticket.status == TICKET_OPEN:
        ticket.status = TICKET_CLAIMED
        ticket.claimed_by = current_user.id

    db.commit()
    db.refresh(message)

    create_notification(
        db,
        user_id=ticket.user_id,
        title="New specialist reply",
        message=(
            f"A specialist replied to your request "
            f"'{ticket.subject}'."
        ),
        type="info",
        link="/dashboard/support",
    )

    users = _user_lookup(db)
    return _message_payload(message, users)


@router.post("/specialist/tickets/{ticket_id}/claim", response_model=SupportTicketOut)
def claim_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_specialist_user),
):
    """Mark a ticket as being worked by the current specialist."""
    ticket = _get_any_ticket(ticket_id, db)

    if ticket.status == TICKET_RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A resolved ticket cannot be claimed; reopen it first.",
        )

    ticket.status = TICKET_CLAIMED
    ticket.claimed_by = current_user.id
    db.commit()
    db.refresh(ticket)

    users = _user_lookup(db)
    return _ticket_payload(ticket, SENDER_SPECIALIST, db, users)


@router.post("/specialist/tickets/{ticket_id}/resolve", response_model=SupportTicketOut)
def resolve_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_specialist_user),
):
    """Close a ticket as resolved."""
    ticket = _get_any_ticket(ticket_id, db)

    ticket.status = TICKET_RESOLVED
    ticket.resolved_by = current_user.id
    ticket.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ticket)

    create_notification(
        db,
        user_id=ticket.user_id,
        title="Request resolved",
        message=f"Your request '{ticket.subject}' has been resolved.",
        type="success",
        link="/dashboard/support",
    )

    users = _user_lookup(db)
    return _ticket_payload(ticket, SENDER_SPECIALIST, db, users)


@router.post("/specialist/tickets/{ticket_id}/reopen", response_model=SupportTicketOut)
def reopen_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_specialist_user),
):
    """Reopen a resolved ticket."""
    ticket = _get_any_ticket(ticket_id, db)

    ticket.status = TICKET_OPEN
    ticket.resolved_by = None
    ticket.resolved_at = None
    ticket.claimed_by = None
    db.commit()
    db.refresh(ticket)

    users = _user_lookup(db)
    return _ticket_payload(ticket, SENDER_SPECIALIST, db, users)
