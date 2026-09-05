import json
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import (
    AssistantAttachment,
    AssistantConversation,
    AssistantMessage,
    ConfigurationRequest,
    ConfigurationTask,
    User,
)
from ..db.deps import get_current_user
from ..schemas.assistant import (
    AssistantAttachmentOut,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantConversationSummary,
    AssistantMessageOut,
)
from ..services.document_service import build_docx, build_pdf
from ..services.groq_service import (
    get_assistant_chat_response,
    get_assistant_followup_suggestions,
    is_document_related_to_brainopx,
)
from ..services.rule_parser import extract_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

ATTACHMENT_UPLOAD_DIR = os.path.join("uploads", "assistant", "attachments")
os.makedirs(ATTACHMENT_UPLOAD_DIR, exist_ok=True)

ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".csv"}
MAX_ATTACHMENT_SIZE = 15 * 1024 * 1024  # 15MB

# Per-document / total cap on how much extracted text is fed into a single
# chat turn's prompt, independent of how much is kept in the DB.
ATTACHMENT_CONTEXT_PER_DOC_CHARS = 8_000
ATTACHMENT_CONTEXT_TOTAL_CHARS = 16_000


def _get_owned_conversation(conversation_id: int, current_user: User, db: Session) -> AssistantConversation:
    conversation = (
        db.query(AssistantConversation)
        .filter(AssistantConversation.id == conversation_id)
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    if conversation.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation.")

    return conversation


def _build_task_context(task_id: int, db: Session) -> str:
    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    rules_text = ""
    if task.rules_content:
        try:
            rules_text = json.loads(task.rules_content).get("full_text", "") or ""
        except (json.JSONDecodeError, TypeError, ValueError):
            rules_text = task.rules_content or ""

    status_counts = dict(
        db.query(ConfigurationRequest.status, func.count(ConfigurationRequest.id))
        .filter(ConfigurationRequest.task_id == task_id)
        .group_by(ConfigurationRequest.status)
        .all()
    )
    total_requests = sum(status_counts.values())

    context = f"""Name: {task.name}
Description: {task.description or "(none)"}
Category: {task.category}
Target table: {task.target_table or "(none)"}
Active: {task.is_active}

Submitted requests for this task: {total_requests} total
Breakdown by status: {json.dumps(status_counts) if status_counts else "(no requests yet)"}
"""

    if rules_text:
        context += f"\nRules document:\n{rules_text[:12000]}\n"

    return context


def _attachment_url(stored_path: str) -> str:
    return "/" + stored_path.replace(os.sep, "/").lstrip("/")


def _attachment_out(attachment: AssistantAttachment) -> AssistantAttachmentOut:
    return AssistantAttachmentOut(
        id=attachment.id,
        filename=attachment.original_filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        url=_attachment_url(attachment.stored_path),
        extractable=attachment.extractable,
    )


def _off_topic_attachment_message(language: str, filenames: list[str]) -> str:
    """
    Canned reply used instead of calling the AI when one or more attached
    documents aren't related to BRAINOPX — the assistant should refuse to
    read/summarize such a file rather than analyze whatever it contains.
    """

    names = ", ".join(f'"{name}"' for name in filenames)
    plural = len(filenames) > 1

    if language == "fr":
        verb = "ne semblent pas être liés" if plural else "ne semble pas être lié"
        return (
            f"Je ne peux analyser que des documents liés à BRAINOPX (tâches, règles, "
            f"données de configuration ou rapports). {names} {verb} à BRAINOPX. "
            "Merci de téléverser un document lié à BRAINOPX."
        )

    verb = "don't" if plural else "doesn't"
    return (
        f"I can only analyze documents related to BRAINOPX (tasks, rules, "
        f"configuration data, or reports). {names} {verb} appear to be related. "
        "Please upload a document related to BRAINOPX."
    )


def _build_attachment_context(attachments: list[AssistantAttachment]) -> str | None:
    if not attachments:
        return None

    parts = ["ATTACHED DOCUMENTS:"]
    total = 0

    for attachment in attachments:
        text = (attachment.extracted_text or "")[:ATTACHMENT_CONTEXT_PER_DOC_CHARS]
        parts.append(f"--- {attachment.original_filename} ---\n{text}")
        total += len(text)
        if total >= ATTACHMENT_CONTEXT_TOTAL_CHARS:
            break

    return "\n\n".join(parts)


def _delete_attachments_for_conversations(conversation_ids: list[int], db: Session) -> None:
    """Explicit cleanup: attachment FKs use ondelete=SET NULL (not CASCADE, see
    db/models.py for why), so deleting a conversation never cascades to its
    attachments automatically — this must be called before the conversation
    delete/commit, or attachment rows and their files on disk are orphaned."""

    if not conversation_ids:
        return

    attachments = (
        db.query(AssistantAttachment)
        .filter(AssistantAttachment.conversation_id.in_(conversation_ids))
        .all()
    )

    for attachment in attachments:
        try:
            if os.path.exists(attachment.stored_path):
                os.remove(attachment.stored_path)
        except OSError as exc:
            logger.warning("Could not remove attachment file %s: %s", attachment.stored_path, exc)

        db.delete(attachment)


@router.post("/attachments", response_model=AssistantAttachmentOut)
def upload_attachment(
    file: UploadFile = File(...),
    conversation_id: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attaches a document (PDF/Word/Excel/CSV/text) to the assistant chat.

    Uploaded standalone, ahead of the message it will be sent with (the user
    picks a file, then types and sends) — conversation_id is optional here
    and message_id is filled in later, once /chat actually uses it.
    """

    ext = os.path.splitext(file.filename or "")[1].lower()

    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Allowed: PDF, Word, Excel, CSV, or plain text.",
        )

    if conversation_id is not None:
        _get_owned_conversation(conversation_id, current_user, db)

    data = file.file.read()

    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")

    if len(data) > MAX_ATTACHMENT_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is too large (15MB max).")

    unique_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(ATTACHMENT_UPLOAD_DIR, unique_name)

    with open(stored_path, "wb") as buffer:
        buffer.write(data)

    try:
        extracted_text = extract_text(stored_path)[:20_000]
        extractable = True
    except Exception as exc:
        logger.warning("Could not extract text from assistant attachment %r: %s", file.filename, exc)
        extracted_text = "[No extractable text found in this file.]"
        extractable = False

    attachment = AssistantAttachment(
        user_id=current_user.id,
        conversation_id=conversation_id,
        original_filename=file.filename or unique_name,
        stored_path=stored_path,
        content_type=file.content_type,
        size_bytes=len(data),
        extracted_text=extracted_text,
        extractable=extractable,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return _attachment_out(attachment)


@router.post("/chat", response_model=AssistantChatResponse)
def chat(
    payload: AssistantChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.conversation_id:
        conversation = _get_owned_conversation(payload.conversation_id, current_user, db)
    else:
        conversation = AssistantConversation(user_id=current_user.id)
        db.add(conversation)
        db.flush()

    task_context = _build_task_context(payload.task_id, db) if payload.task_id else None

    attachments: list[AssistantAttachment] = []
    if payload.attachment_ids:
        attachments = (
            db.query(AssistantAttachment)
            .filter(
                AssistantAttachment.id.in_(payload.attachment_ids),
                AssistantAttachment.user_id == current_user.id,
            )
            .all()
        )

        missing = set(payload.attachment_ids) - {a.id for a in attachments}
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment(s) not found: {sorted(missing)}",
            )

        # Attachments are single-use: bound to exactly one message so an
        # upload can't silently be replayed into an unrelated conversation.
        already_used = [a.original_filename for a in attachments if a.message_id is not None]
        if already_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Already attached to another message: {', '.join(already_used)}",
            )

    # Gate on relevance before the assistant reads/summarizes any attached
    # file: an off-topic upload should be refused, not analyzed. Only
    # extractable attachments are checked — an unreadable file already gets
    # its own "couldn't be read" notice at upload time.
    unrelated_attachments = [
        a
        for a in attachments
        if a.extractable and not is_document_related_to_brainopx(a.original_filename, a.extracted_text)
    ]

    extra_context = _build_attachment_context(attachments)

    history_rows = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.conversation_id == conversation.id)
        .order_by(AssistantMessage.created_at, AssistantMessage.id)
        .all()[-10:]
    )
    conversation_history = [{"role": row.role, "content": row.content} for row in history_rows]

    user_message = AssistantMessage(
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
    )
    db.add(user_message)
    db.flush()

    for attachment in attachments:
        attachment.conversation_id = conversation.id
        attachment.message_id = user_message.id

    if unrelated_attachments:
        reply_text = _off_topic_attachment_message(
            current_user.language,
            [a.original_filename for a in unrelated_attachments],
        )
        suggestions: list[str] = []
    else:
        reply_text = get_assistant_chat_response(
            user_message=payload.message,
            conversation_history=conversation_history,
            task_context=task_context,
            extra_context=extra_context,
            language=current_user.language,
        )
        # Follow-up chips for the composer once this turn completes — best
        # effort, so a failure here never blocks the reply itself.
        suggestions = get_assistant_followup_suggestions(
            user_message=payload.message,
            assistant_reply=reply_text,
            language=current_user.language,
        )

    reply_message = AssistantMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=reply_text,
    )
    db.add(reply_message)

    if not conversation.title:
        conversation.title = payload.message.strip()[:60]

    db.commit()
    db.refresh(reply_message)

    return AssistantChatResponse(
        conversation_id=conversation.id,
        reply=AssistantMessageOut(
            id=reply_message.id,
            role=reply_message.role,
            content=reply_message.content,
            created_at=reply_message.created_at,
            attachments=[_attachment_out(a) for a in attachments],
            suggestions=suggestions,
        ),
    )


@router.get("/conversations", response_model=list[AssistantConversationSummary])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversations = (
        db.query(AssistantConversation)
        .filter(AssistantConversation.user_id == current_user.id)
        .order_by(AssistantConversation.updated_at.desc())
        .all()
    )

    summaries = []
    for conversation in conversations:
        last_message = (
            db.query(AssistantMessage)
            .filter(AssistantMessage.conversation_id == conversation.id)
            .order_by(AssistantMessage.created_at.desc(), AssistantMessage.id.desc())
            .first()
        )
        summaries.append(
            AssistantConversationSummary(
                id=conversation.id,
                title=conversation.title,
                updated_at=conversation.updated_at,
                last_message_preview=(last_message.content[:120] if last_message else None),
            )
        )

    return summaries


@router.delete("/conversations")
def clear_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes every assistant conversation belonging to the current user."""

    conversations = (
        db.query(AssistantConversation)
        .filter(AssistantConversation.user_id == current_user.id)
        .all()
    )
    conversation_ids = [c.id for c in conversations]

    _delete_attachments_for_conversations(conversation_ids, db)

    db.query(AssistantConversation).filter(
        AssistantConversation.user_id == current_user.id
    ).delete(synchronize_session=False)
    db.commit()

    return {"message": "All conversations deleted.", "success": True}


@router.get("/conversations/{conversation_id}", response_model=list[AssistantMessageOut])
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_conversation(conversation_id, current_user, db)

    messages = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.conversation_id == conversation_id)
        .order_by(AssistantMessage.created_at, AssistantMessage.id)
        .all()
    )

    message_ids = [m.id for m in messages]
    attachments_by_message: dict[int, list[AssistantAttachment]] = {}
    if message_ids:
        for row in (
            db.query(AssistantAttachment)
            .filter(AssistantAttachment.message_id.in_(message_ids))
            .all()
        ):
            attachments_by_message.setdefault(row.message_id, []).append(row)

    return [
        AssistantMessageOut(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            attachments=[_attachment_out(a) for a in attachments_by_message.get(message.id, [])],
        )
        for message in messages
    ]


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation = _get_owned_conversation(conversation_id, current_user, db)

    _delete_attachments_for_conversations([conversation.id], db)

    db.delete(conversation)
    db.commit()

    return {"message": "Conversation deleted.", "success": True}


@router.get("/conversations/{conversation_id}/export")
def export_conversation(
    conversation_id: int,
    format: str = "pdf",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if format not in ("pdf", "docx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="format must be 'pdf' or 'docx'.")

    conversation = _get_owned_conversation(conversation_id, current_user, db)

    messages = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.conversation_id == conversation_id)
        .order_by(AssistantMessage.created_at, AssistantMessage.id)
        .all()
    )

    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This conversation has no messages to export.",
        )

    message_ids = [m.id for m in messages]
    attachment_names_by_message: dict[int, list[str]] = {}
    if message_ids:
        for row in (
            db.query(AssistantAttachment)
            .filter(AssistantAttachment.message_id.in_(message_ids))
            .all()
        ):
            attachment_names_by_message.setdefault(row.message_id, []).append(row.original_filename)

    turns = []
    for message in messages:
        speaker = "You" if message.role == "user" else "Assistant"
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M") if message.created_at else ""
        content = message.content
        for filename in attachment_names_by_message.get(message.id, []):
            content += f"\n\n[Attached: {filename}]"
        turns.append((speaker, timestamp, content))

    title = conversation.title or "BRAINOPX Assistant Conversation"
    date_str = datetime.utcnow().strftime("%Y%m%d")
    filename = f"brainopx-assistant-{conversation_id}-{date_str}.{format}"

    if format == "pdf":
        content_bytes = build_pdf(title, turns)
        media_type = "application/pdf"
    else:
        content_bytes = build_docx(title, turns)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return Response(
        content=content_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
