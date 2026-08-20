import os
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session

from ..db.database import get_db, engine
from ..db.models import ConfigurationTask, User
from ..db.deps import get_current_user, get_current_admin_user
from ..schemas.task import TaskResponse
from ..services.excel_service import extract_column_headers, read_data_rows
from ..services.schema_introspection import get_table_column_rules
from ..services.rule_parser import extract_text  # ✅ Correct import
from ..services.groq_service import parse_rules_to_json, get_ai_response
from ..services.example_utils import build_rules_with_examples

from ..services.skill_engine_service import get_rules_for_task, parse_task_rules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

UPLOAD_DIR = os.path.join("uploads", "templates")
RULES_UPLOAD_DIR = os.path.join("uploads", "rules")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RULES_UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS_BY_CATEGORY = {
    "report_analyses": {".xlsx"},
    "skill_engine": {".txt", ".pdf", ".doc", ".docx"},
}
ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS_BY_CATEGORY.get("report_analyses", {".xlsx"})
ALLOWED_RULES_EXTENSIONS = {".pdf", ".txt", ".docx"}


def _store_rules_with_examples(task, rules_text: str):
    """
    Parses the rules document text into structured rules and enriches each rule
    with its correct `example_input` value (derived from that rule's own format).
    The enriched rules are stored on the task's `category_metadata.parsed_rules`
    so they are available immediately wherever rules are used.

    This runs automatically at task creation / update time.
    Returns the enriched rules list (or [] if parsing fails).
    """
    try:
        rules = parse_rules_to_json(rules_text)
    except Exception:
        # Parsing needs the AI service; a failure here is worth seeing,
        # not swallowing. The task is still created without rules.
        logger.exception(
            "Could not parse the rules document for task '%s'",
            getattr(task, "name", "unknown"),
        )
        return []

    try:
        rules = build_rules_with_examples(rules)
    except Exception:
        logger.exception(
            "Could not build examples for the rules of task '%s'",
            getattr(task, "name", "unknown"),
        )
        return []

    if not rules:
        logger.warning(
            "Rules document for task '%s' produced no rules.",
            getattr(task, "name", "unknown"),
        )
        return []

    metadata = {}
    if task.category_metadata:
        try:
            metadata = json.loads(task.category_metadata) or {}
        except (json.JSONDecodeError, TypeError, ValueError):
            metadata = {}
    if rules:
        metadata["parsed_rules"] = rules
        task.category_metadata = json.dumps(metadata)
    return rules


def _task_to_response(task: ConfigurationTask) -> dict:
    # Get actual file size from disk
    file_size_bytes = 0
    if task.template_file_path and os.path.exists(task.template_file_path):
        file_size_bytes = os.path.getsize(task.template_file_path)

    # Safely parse expected_columns JSON
    try:
        expected_columns = json.loads(task.expected_columns) if task.expected_columns else []
    except (json.JSONDecodeError, TypeError, ValueError):
        expected_columns = []

    # Safely parse column_rules JSON
    column_rules = None
    if task.column_rules:
        try:
            column_rules = json.loads(task.column_rules)
        except (json.JSONDecodeError, TypeError, ValueError):
            column_rules = None

    # Safely parse category_metadata JSON
    category_metadata = None
    if task.category_metadata:
        try:
            category_metadata = json.loads(task.category_metadata)
        except (json.JSONDecodeError, TypeError, ValueError):
            category_metadata = None

    # Safely parse rules_content JSON
    rules_content = None
    if task.rules_content:
        try:
            rules_content = json.loads(task.rules_content)
        except (json.JSONDecodeError, TypeError, ValueError):
            rules_content = None

    return {
        "id": task.id,
        "name": task.name,
        "description": task.description,

        "category": task.category or "other",
        "template_filename": task.template_filename,
        "template_file_size": file_size_bytes,
        "template_file_size_kb": round(file_size_bytes / 1024, 1) if file_size_bytes else 0,
        "expected_columns": expected_columns,
        "target_table": task.target_table,
        "column_rules": column_rules,
        "category_metadata": category_metadata,
        "rules_document_filename": task.rules_document_filename if hasattr(task, 'rules_document_filename') else None,
        "rules_content": rules_content,
        "is_active": task.is_active,
        "created_at": task.created_at,
        "template_data": None,
    }


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form("other"),
    target_table: str = Form(""),
    file: UploadFile = File(None),
    rules_file: UploadFile = File(None),
    category_metadata: str = Form("null"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Create a new configuration task. Admin only — everyone else can
    still list, view, run and even edit/delete existing tasks; only
    defining a new one is restricted.
    - For 'report_analyses' category: Excel template is required
    - For 'skill_engine' category: Rules document is required
    """

    # Validate: At least one of file or rules_file must be provided
    if not file and not rules_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either an Excel template or a Rules document must be provided."
        )

    # Handle Excel template upload (optional)
    template_filename = None
    template_file_path = None
    expected_columns = None
    template_file_size = 0

    if file:
        ext = os.path.splitext(file.filename)[1].lower()
        allowed = ALLOWED_EXTENSIONS_BY_CATEGORY.get(category, ALLOWED_EXTENSIONS_BY_CATEGORY["report_analyses"])
        if ext not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {ext} not allowed for category '{category}'.",
            )

        unique_name = f"{uuid.uuid4().hex}{ext}"
        saved_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(saved_path, "wb") as buffer:
            buffer.write(file.file.read())

        template_filename = file.filename
        template_file_path = saved_path
        template_file_size = os.path.getsize(saved_path)

        # Extract Excel column headers only for report_analyses tasks
        if category == "report_analyses":
            expected_columns = json.dumps(extract_column_headers(saved_path))
        else:
            expected_columns = "[]"

    # Handle Rules document upload
    rules_document_filename = None
    rules_document_path = None
    rules_content = None
    rules_text = None

    if rules_file:
        rules_ext = os.path.splitext(rules_file.filename)[1].lower()
        if rules_ext not in ALLOWED_RULES_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rules file must be PDF, TXT, or DOCX.",
            )

        rules_unique_name = f"rules_{uuid.uuid4().hex}{rules_ext}"
        rules_saved_path = os.path.join(RULES_UPLOAD_DIR, rules_unique_name)
        with open(rules_saved_path, "wb") as buffer:
            buffer.write(rules_file.file.read())

        rules_document_filename = rules_file.filename
        rules_document_path = rules_saved_path

        # ✅ Extract text from rules document using rule_parser
        rules_text = extract_text(rules_saved_path)

        # Store the full text in the task for AI use
        rules_content = json.dumps({
            "full_text": rules_text,
        })

    # Get column rules from target table if provided
    column_rules = None
    target_table_clean = target_table.strip() or None
    if target_table_clean:
        column_rules = get_table_column_rules(engine, target_table_clean)

    # Parse category_metadata if provided
    parsed_category_metadata = None
    if category_metadata and category_metadata != "null":
        try:
            parsed_category_metadata = json.loads(category_metadata)
        except (json.JSONDecodeError, TypeError, ValueError):
            parsed_category_metadata = None

    # Create the task with all fields
    new_task = ConfigurationTask(
        name=name,
        description=description,
        category=category,
        template_filename=template_filename,
        template_file_path=template_file_path,
        expected_columns=expected_columns or "[]",
        target_table=target_table_clean,
        column_rules=json.dumps(column_rules) if column_rules else None,
        category_metadata=json.dumps(parsed_category_metadata) if parsed_category_metadata else None,
        rules_document_filename=rules_document_filename,
        rules_document_path=rules_document_path,
        rules_content=rules_content,
        created_by=current_user.id,
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    # ✅ Parse the rules document into structured rules and pre-generate a
    # correct example input for each rule/step. This is stored so the AI
    # assistant can show the right example for every step automatically.
    if rules_text:
        _store_rules_with_examples(new_task, rules_text)
        db.commit()
        db.refresh(new_task)

    return _task_to_response(new_task)


@router.get("/", response_model=list[TaskResponse])
def list_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        tasks = db.query(ConfigurationTask).filter(ConfigurationTask.is_active == True).all()
        return [_task_to_response(t) for t in tasks]
    except Exception as e:
        print(f"ERROR in list_tasks: {str(e)}")  # This will show in terminal
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading tasks: {str(e)}"
        )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    response = _task_to_response(task)

    # Read Excel data rows from the template file (only for report_analyses)
    if task.category == "report_analyses" and task.template_file_path and os.path.exists(task.template_file_path):
        try:
            data_rows = read_data_rows(task.template_file_path)
            clean_rows = []
            for row in data_rows:
                clean_row = {k: v for k, v in row.items() if k != "_row_number"}
                clean_rows.append(clean_row)
            response["template_data"] = clean_rows
        except Exception:
            response["template_data"] = []

    return response


@router.get("/{task_id}/rules")
def get_task_rules(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get the rules content for a specific task.
    Used by the AI to guide the user.
    """
    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    # ✅ Try to get rules from skill_engine_service first
    skill_rules = get_rules_for_task(db, task_id)
    if skill_rules:
        return {
            "id": task.id,
            "name": task.name,

            "rules": skill_rules,
            "source": "skill_engine"
        }

    # ✅ Fallback to rules_content from task
    rules_content = json.loads(task.rules_content) if task.rules_content else {}

    return {
        "id": task.id,
        "name": task.name,

        "rules": [],
        "summary": rules_content.get("full_text", "")[:1000] + "...",
        "full_text": rules_content.get("full_text", ""),
        "source": "task_rules"
    }


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    name: str = Form(None),
    description: str = Form(""),
    category: str = Form(None),
    target_table: str = Form(""),
    file: UploadFile = File(None),
    rules_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing configuration task.
    """
    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )

    # Update basic fields if provided
    if name:
        task.name = name
    if description is not None:
        task.description = description
    if category is not None:
        task.category = category
    if target_table is not None:
        target_table_clean = target_table.strip() or None
        task.target_table = target_table_clean
        if target_table_clean:
            task.column_rules = json.dumps(get_table_column_rules(engine, target_table_clean))

    # Update template file if provided
    if file:
        ext = os.path.splitext(file.filename)[1].lower()
        effective_category = category or task.category or "report_analyses"
        allowed = ALLOWED_EXTENSIONS_BY_CATEGORY.get(effective_category, ALLOWED_EXTENSIONS_BY_CATEGORY["report_analyses"])
        if ext not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {ext} not allowed for category '{effective_category}'.",
            )

        # Delete old file
        if task.template_file_path and os.path.exists(task.template_file_path):
            os.remove(task.template_file_path)

        # Save new file
        unique_name = f"{uuid.uuid4().hex}{ext}"
        saved_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(saved_path, "wb") as buffer:
            buffer.write(file.file.read())

        task.template_file_path = saved_path
        task.template_filename = file.filename
        if effective_category == "report_analyses":
            task.expected_columns = json.dumps(extract_column_headers(saved_path))
        else:
            task.expected_columns = "[]"

    # ✅ Update rules document if provided
    rules_text = None
    if rules_file:
        rules_ext = os.path.splitext(rules_file.filename)[1].lower()
        if rules_ext not in ALLOWED_RULES_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rules file must be PDF, TXT, or DOCX.",
            )

        # Delete old rules file
        if task.rules_document_path and os.path.exists(task.rules_document_path):
            os.remove(task.rules_document_path)

        # Save new rules file
        rules_unique_name = f"rules_{uuid.uuid4().hex}{rules_ext}"
        rules_saved_path = os.path.join(RULES_UPLOAD_DIR, rules_unique_name)
        with open(rules_saved_path, "wb") as buffer:
            buffer.write(rules_file.file.read())

        task.rules_document_filename = rules_file.filename
        task.rules_document_path = rules_saved_path

        # ✅ Extract text from rules document using rule_parser
        rules_text = extract_text(rules_saved_path)

        task.rules_content = json.dumps({
            "full_text": rules_text,
        })

    db.commit()
    db.refresh(task)

    # ✅ Re-parse the updated rules document and pre-generate a correct example
    # input for each rule/step so the AI assistant always has the right example.
    if rules_text:
        _store_rules_with_examples(task, rules_text)
        db.commit()
        db.refresh(task)

    return _task_to_response(task)


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a configuration task by ID (soft delete).
    """
    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == task_id).first()

    if not task:
        return {"message": "Task already deleted", "success": True}

    # Soft delete - mark as inactive
    task.is_active = False
    db.commit()

    return {"message": f"Task '{task.name}' deleted successfully", "success": True}


@router.get("/explain")
def explain_task(
    task_id: int = Query(..., description="The ID of the task to explain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns an AI-generated explanation of the task, including rule-based
    example inputs for each step, derived strictly from the task's rules content.
    """
    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    rules_text = ""
    if task.rules_content:
        try:
            rules_content_obj = json.loads(task.rules_content)
            rules_text = rules_content_obj.get("full_text", "") or ""
        except (json.JSONDecodeError, TypeError, ValueError):
            rules_text = task.rules_content or ""

    category_metadata = None
    if task.category_metadata:
        try:
            category_metadata = json.loads(task.category_metadata)
        except (json.JSONDecodeError, TypeError, ValueError):
            category_metadata = None

    parsed_rules = []
    if isinstance(category_metadata, dict):
        parsed_rules = category_metadata.get("parsed_rules", []) or []

    explanation = get_ai_response(
        task_name=task.name,
        validation_errors=[],
        conversation_history=[],
        user_message=(
            "Guide me through creating this task step by step. "
            "Start by acknowledging the rules, then break them into numbered steps. "
            "For each step, provide an instruction and ONE concrete example input. "
            "Wait for my input before moving to the next step."
        ),
        rules_content=rules_text,
        parsed_rules=parsed_rules,
        mode="task_creation_guide",
    )

    return {
        "task_id": task.id,
        "task_name": task.name,
        "explanation": explanation,
    }
