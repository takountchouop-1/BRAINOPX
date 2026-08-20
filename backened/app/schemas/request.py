from pydantic import BaseModel
from datetime import datetime
from typing import Any


class RequestResponse(BaseModel):
    id: int
    task_id: int
    status: str
    uploaded_filename: str | None
    validation_errors: list[dict[str, Any]]
    eval_profile: dict[str, Any] | None
    conversation: list[dict[str, Any]]
    generated_script: str | None
    created_at: datetime

    class Config:
        from_attributes = True