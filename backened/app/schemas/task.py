from pydantic import BaseModel
from datetime import datetime
from typing import Any


class TaskResponse(BaseModel):
    id: int
    name: str
    description: str | None
    category: str = "other"
    template_filename: str
    template_file_size: int = 0
    template_file_size_kb: float = 0.0
    expected_columns: list[str]
    target_table: str | None
    column_rules: list[dict[str, Any]] | None
    category_metadata: dict[str, Any] | None = None
    is_active: bool
    created_at: datetime
    template_data: list[dict[str, Any]] | None = None

    class Config:
        from_attributes = True
