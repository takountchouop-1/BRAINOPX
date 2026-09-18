import logging
import os
import secrets
import shutil
import string
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..db.models import User
from ..db.deps import get_current_user, get_current_admin_user
from ..core.security import hash_password
from ..core.email_service import send_new_user_email
from ..schemas.user import (
    UserUpdate,
    UserResponse,
    UserAdminResponse,
    UserCreateByAdmin,
    UserAdminUpdate,
)
from ..services import user_access

router = APIRouter(prefix="/api/users", tags=["users"])

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join("uploads", "profiles")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _to_admin_response(user: User) -> UserAdminResponse:
    return UserAdminResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        profile_picture=user.profile_picture,
        is_active=user.is_active,
        role=user.role,
        access=user_access.parse_access(user.access),
        address=user.address,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _generate_temporary_password() -> str:
    """
    A 12-character password an admin never has to invent or see
    typed — letters, digits and one punctuation mark from each side,
    generated with `secrets` rather than `random`.
    """
    alphabet = string.ascii_letters + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(10))
    return f"{body[:5]}#{body[5:]}!"


@router.get("/")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Every user, for the User Management page. Admin only — the
    response includes each user's email, address and last login, so
    it's restricted the same as creating/editing/deleting users.
    """

    users = db.query(User).order_by(User.created_at.desc()).all()

    return {
        "summary": {
            "total": len(users),
            "admins": sum(1 for u in users if u.role == user_access.ROLE_ADMIN),
            "active": sum(1 for u in users if u.is_active),
        },
        "items": [_to_admin_response(u) for u in users],
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateByAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Create a user. Admin only.

    A temporary password is generated here rather than supplied by
    the admin, so no one but the new user ever needs to know it. It
    is returned once in this response and best-effort emailed — an
    unreachable or unconfigured mail server does not block account
    creation, since the admin still has the password to hand over.
    """

    email = str(body.email).strip().lower()

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    role = body.role if body.role in user_access.ROLES else user_access.ROLE_MEMBER

    temporary_password = _generate_temporary_password()

    new_user = User(
        full_name=body.full_name.strip(),
        email=email,
        hashed_password=hash_password(temporary_password),
        address=(body.address or "").strip() or None,
        role=role,
        access=user_access.encode_access(body.access),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    email_sent = True
    try:
        send_new_user_email(new_user.email, new_user.full_name, temporary_password)
    except Exception:
        email_sent = False
        logger.warning(
            "Could not email the temporary password for user %s; "
            "the admin still has it in the API response.",
            new_user.id,
        )

    return {
        "user": _to_admin_response(new_user),
        "temporary_password": temporary_password,
        "email_sent": email_sent,
    }


@router.patch("/{user_id}", response_model=UserAdminResponse)
def update_user_access(
    user_id: int,
    body: UserAdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Change a user's role, access tags, address, or active status.
    Admin only.
    """

    target = db.query(User).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # An admin cannot strip their own admin role or lock their own
    # account through this endpoint — the classic guard against an
    # admin accidentally leaving nobody able to manage the team.
    is_self = target.id == current_user.id

    if body.role is not None:
        if body.role not in user_access.ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role must be one of: {', '.join(user_access.ROLES)}.",
            )
        if is_self and body.role != user_access.ROLE_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot remove your own administrator role.",
            )
        target.role = body.role

    if body.access is not None:
        target.access = user_access.encode_access(body.access)

    if body.address is not None:
        target.address = body.address.strip() or None

    if body.is_active is not None:
        if is_self and not body.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate your own account.",
            )
        target.is_active = body.is_active

    db.commit()
    db.refresh(target)

    return _to_admin_response(target)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Permanently remove a user. Admin only.

    Unlike deactivating (PATCH is_active=False), this cannot be
    undone, so it is refused whenever the account has real history
    attached — configuration requests, skill-engine runs, or guided
    walkthroughs. None of those tables cascade from users (they hold
    a person's actual work), so deleting a user who has any would
    either destroy that history silently or fail with a raw database
    constraint error; refusing up front with a clear reason is safer
    than either. Deactivating is offered as the reversible
    alternative in that case.

    Notifications DO cascade at the model level, but that constraint
    is only guaranteed on a table created fresh by this schema — an
    existing database may predate it — so they are deleted explicitly
    here rather than assumed away.
    """

    from ..db.models import (
        ConfigurationRequest,
        ConfigurationTask,
        Notification,
        SkillEngineRun,
        GuidedSession,
        SupportMessage,
        SupportTicket,
    )

    target = db.query(User).filter(User.id == user_id).first()

    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    history = {
        "configuration request": db.query(ConfigurationRequest)
        .filter(ConfigurationRequest.user_id == target.id).count(),
        "skill-engine run": db.query(SkillEngineRun)
        .filter(SkillEngineRun.user_id == target.id).count(),
        "guided walkthrough": db.query(GuidedSession)
        .filter(GuidedSession.user_id == target.id).count(),
    }

    blocking = {label: count for label, count in history.items() if count > 0}

    if blocking:
        parts = ", ".join(f"{count} {label}{'s' if count != 1 else ''}" for label, count in blocking.items())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{target.full_name} has {parts} and cannot be deleted. "
                f"Deactivate the account instead to revoke access while keeping their history."
            ),
        )

    # Authorship of a task is metadata, not the target's own work —
    # freeing it rather than blocking the whole deletion over it.
    db.query(ConfigurationTask).filter(ConfigurationTask.created_by == target.id).update(
        {"created_by": None}
    )

    db.query(Notification).filter(Notification.user_id == target.id).delete()

    # Support threads are the target's own work, not system history —
    # remove them rather than block the deletion. The ticket's messages
    # cascade with the ticket itself, and any ticket the target was
    # merely claimed-by/resolved-by on has that pointer cleared.
    db.query(SupportMessage).filter(SupportMessage.sender_id == target.id).delete()
    db.query(SupportTicket).filter(SupportTicket.user_id == target.id).delete()
    db.query(SupportTicket).filter(SupportTicket.claimed_by == target.id).update(
        {"claimed_by": None}
    )
    db.query(SupportTicket).filter(SupportTicket.resolved_by == target.id).update(
        {"resolved_by": None}
    )

    if target.profile_picture:
        old_path = os.path.join(UPLOAD_DIR, target.profile_picture)
        if os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError:
                logger.warning("Could not remove profile picture for deleted user %s", target.id)

    db.delete(target)
    db.commit()

    return {"deleted": True, "id": user_id}


@router.put("/profile", response_model=UserResponse)
def update_profile(
    update_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the current user's profile (full_name, email, and/or language).
    """
    # Validate and update email
    if update_data.email is not None:
        # Check if email is already taken by another user
        existing = db.query(User).filter(
            User.email == update_data.email,
            User.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email is already in use by another account."
            )
        current_user.email = update_data.email

    # Validate and update full_name
    if update_data.full_name is not None:
        current_user.full_name = update_data.full_name

    # Validate and update language
    if update_data.language is not None:
        if update_data.language not in ("en", "fr"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Language must be 'en' or 'fr'.",
            )
        current_user.language = update_data.language

    db.commit()
    db.refresh(current_user)

    return current_user


@router.post("/upload-profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a profile picture for the current user.
    """
    # Validate file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files (jpg, jpeg, png, gif, webp) are allowed."
        )
    
    # Validate file size (max 5MB)
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()  # Get file size
    file.file.seek(0)  # Seek back to start
    
    if file_size > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size must be less than 5MB."
        )
    
    # Delete old profile picture if exists
    if current_user.profile_picture:
        old_path = os.path.join(UPLOAD_DIR, current_user.profile_picture)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass
    
    # Save new file
    unique_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, unique_name)
    
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Update user in database
    current_user.profile_picture = unique_name
    db.commit()
    
    # Return the full URL
    profile_url = f"/uploads/profiles/{unique_name}"
    
    return {
        "message": "Profile picture uploaded successfully",
        "profile_picture": unique_name,
        "profile_url": profile_url
    }


@router.delete("/profile-picture")
def delete_profile_picture(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete the current user's profile picture.
    """
    if not current_user.profile_picture:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile picture found."
        )
    
    # Delete file
    file_path = os.path.join(UPLOAD_DIR, current_user.profile_picture)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass
    
    # Update user in database
    current_user.profile_picture = None
    db.commit()
    
    return {"message": "Profile picture deleted successfully"}