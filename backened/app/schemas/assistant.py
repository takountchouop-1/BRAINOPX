from pydantic import BaseModel
from datetime import datetime


class AssistantChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None
    task_id: int | None = None
    attachment_ids: list[int] | None = None


class AssistantAttachmentOut(BaseModel):
    id: int
    filename: str
    content_type: str | None = None
    size_bytes: int | None = None
    url: str
    extractable: bool = True

    class Config:
        from_attributes = True


class AssistantMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    attachments: list[AssistantAttachmentOut] = []
    # Follow-up chips for a reply that was just generated. Not persisted —
    # always empty when a message comes back from conversation history.
    suggestions: list[str] = []

    class Config:
        from_attributes = True


class AssistantChatResponse(BaseModel):
    conversation_id: int
    reply: AssistantMessageOut


class AssistantConversationSummary(BaseModel):
    id: int
    title: str | None
    updated_at: datetime
    last_message_preview: str | None
