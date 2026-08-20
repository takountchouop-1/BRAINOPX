"""
Notification service — creates in-app notifications for the BRAINOPX system.
"""
from typing import Optional
from sqlalchemy.orm import Session
from ..db.models import Notification


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: Optional[str] = None,
    type: str = "info",
    link: Optional[str] = None,
) -> Notification:
    """
    Create a new notification for a user.
    
    Args:
        db: Database session
        user_id: The recipient user's ID
        title: Short notification title (required)
        message: Optional longer description
        type: One of 'info', 'success', 'warning', 'error'
        link: Optional frontend route to link to (e.g. '/dashboard/request/5')
    
    Returns:
        The created Notification object
    """
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type,
        link=link,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

