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
from ..services import excel_rule_parser
from ..services.schema_introspection import get_table_column_rules
from ..services.validation_service import infer_column_rules, infer_formula_rules
from ..services.rule_parser import extract_text  # ✅ Correct import
from ..services.groq_service import parse_rules_to_json, get_ai_response
from ..services.example_utils import build_rules_with_examples
from ..services.task_validator import validate_task_definition

from ..services.skill_engine_service import get_rules_for_task, parse_task_rules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

UPLOAD_DIR = os.path.join("uploads", "templates")
RULES_UPLOAD_DIR = os.path.join("uploads", "rules")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RULES_UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS_BY_CATEGORY = {
    "report_analyses": {".xlsx", ".xlsm"},
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

        # Flag, don't block: an under-specified rule still saves and
        # activates normally, but the admin who authored it can see
        # exactly which rules the engine cannot judge reliably instead
        # of finding out from a user mid-walkthrough.
        try:
            validation_report = validate_task_definition(rules)
        except Exception:
            logger.exception(
                "Could not validate the task definition for task '%s'",
                getattr(task, "name", "unknown"),
            )
            validation_report = None

        if validation_report is not None:
            metadata["validation_report"] = validation_report

            if validation_report["issue_count"]:
                logger.warning(
                    "Task '%s' has %d rule(s) that may be underspecified: %s",
                    getattr(task, "name", "unknown"),
                    validation_report["issue_count"],
                    ", ".join(
                        issue["rule_name"]
                        for issue in validation_report["issues"]
                    ),
                )

        task.category_metadata = json.dumps(metadata)
    return rules


def _merge_excel_column_rules(column_rules: list, extracted: list) -> list:
    """
    Folds excel_rule_parser's deterministic rules into an existing
    column_rules list.

    A data-validation-derived rule (rule_type "cell") merges its
    constraint keys onto the existing rule for the same column name,
    the same "deterministic constraints win" precedent
    groq_service._merge_sql_rules already sets for SQL-derived rules.
    A formula rule for a column already carrying one REPLACES it rather
    than being appended alongside it — needed so re-running this (e.g.
    the rescan-excel-rules endpoint) against the same template is
    idempotent instead of piling up duplicate formula rules each time.
    """
    by_name = {r["name"]: r for r in column_rules if r.get("rule_type", "cell") == "cell"}
    formula_index_by_name = {
        r["name"]: i for i, r in enumerate(column_rules) if r.get("rule_type") == "formula"
    }
    merged = list(column_rules)

    for rule in extracted:
        if rule.get("rule_type") == "formula":
            existing_index = formula_index_by_name.get(rule["name"])
            if existing_index is not None:
                merged[existing_index] = rule
            else:
                merged.append(rule)
                formula_index_by_name[rule["name"]] = len(merged) - 1
            continue

        existing = by_name.get(rule["name"])
        if existing is not None:
            existing.update({k: v for k, v in rule.items() if k != "name"})
        else:
            merged.append(rule)
            by_name[rule["name"]] = rule

    return merged


def _extract_and_merge_excel_rules(template_file_path: str, column_rules: list | None) -> dict:
    """
    Runs both excel_rule_parser (structural: real formulas, data
    validation, conditional formatting, VBA) and
    validation_service.infer_formula_rules (data-driven: a cross-
    column relationship that holds exactly across every sample row,
    for a template that encodes it as plain numbers rather than a live
    formula) against one template file, and merges everything found
    into `column_rules`.

    A structural formula always wins over an inferred one for the
    same column — infer_formula_rules is told to skip any column
    excel_rule_parser already produced a formula for, so the two never
    compete to merge onto the same rule.

    Returns column_rules plus advisory/VBA text plus counts, so a
    caller (creation, update, or the rescan endpoints) can report what
    changed without re-deriving it.
    """
    extracted = excel_rule_parser.extract_excel_business_rules(template_file_path)
    merged = list(column_rules or [])

    if extracted["column_rules"]:
        merged = _merge_excel_column_rules(merged, extracted["column_rules"])

    structural_formula_columns = {
        r["name"] for r in extracted["column_rules"] if r.get("rule_type") == "formula"
    }

    inferred = []
    try:
        headers = extract_column_headers(template_file_path)
        template_rows = read_data_rows(template_file_path)
        inferred = infer_formula_rules(headers, template_rows, exclude_columns=structural_formula_columns)
    except HTTPException:
        pass  # template unreadable for header/row extraction — the structural results above still stand

    if inferred:
        merged = _merge_excel_column_rules(merged, inferred)

    vba_business_rules = []
    if extracted["vba_text"]:
        try:
            vba_business_rules = parse_rules_to_json(extracted["vba_text"])
        except Exception:
            # Best-effort only: VBA is arbitrary code, so a parse
            # failure here just means no business-logic rules were
            # recovered from it this time — the raw macro source is
            # still kept (see excel_vba_text), and nothing else about
            # the task's rules depends on this succeeding.
            logger.exception("Could not parse business-logic rules out of the extracted VBA source.")
            vba_business_rules = []

    return {
        "column_rules": merged,
        "rules_changed": bool(extracted["column_rules"]) or bool(inferred),
        "advisory_notes": extracted["advisory_notes"],
        "vba_text": extracted["vba_text"],
        "vba_business_rules": vba_business_rules,
        "validation_rules_found": sum(
            1 for r in extracted["column_rules"] if r.get("rule_type", "cell") == "cell"
        ),
        "formula_rules_found": sum(1 for r in extracted["column_rules"] if r.get("rule_type") == "formula"),
        "inferred_formula_rules_found": len(inferred),
    }


def _merge_excel_metadata(task: ConfigurationTask, result: dict) -> None:
    """
    Stores whatever _extract_and_merge_excel_rules found beyond
    column_rules — conditional-formatting hints, raw VBA macro source,
    and any business-logic rules Groq could read out of that macro
    source — onto the task's category_metadata. Mutates `task` in
    place; does not commit.

    excel_vba_business_rules is advisory, like the VBA source it comes
    from: nothing in the validation pipeline enforces it automatically
    (VBA is arbitrary code, not a structural artifact like a formula or
    a data-validation rule), but it's visible on the task for an admin
    to review and, if it looks right, turn into an explicit rule.
    """
    if not (result["advisory_notes"] or result["vba_text"] or result.get("vba_business_rules")):
        return

    try:
        metadata = json.loads(task.category_metadata) if task.category_metadata else {}
        if not isinstance(metadata, dict):
            metadata = {}
    except (json.JSONDecodeError, TypeError, ValueError):
        metadata = {}

    if result["advisory_notes"]:
        metadata["excel_advisory_notes"] = result["advisory_notes"]
    if result["vba_text"]:
        metadata["excel_vba_text"] = result["vba_text"]
    if result.get("vba_business_rules"):
        metadata["excel_vba_business_rules"] = result["vba_business_rules"]

    task.category_metadata = json.dumps(metadata)


def _rescan_excel_rules_for_task(task: ConfigurationTask) -> dict:
    """
    Re-runs Excel rule extraction against a report_analyses task's
    already-stored template file and merges anything it finds into the
    task's column_rules / category_metadata — the same thing
    create_task and update_task do at upload time, but callable again
    later for a task whose template predates this extraction, or whose
    template file was replaced on disk without going through the
    upload endpoint.

    Mutates `task` in place. Does not commit — callers own the
    transaction, so a bulk rescan can commit once for every task
    instead of once per task.
    """
    if task.category != "report_analyses":
        return {"skipped": True, "reason": f"category is '{task.category}', not report_analyses"}

    if not task.template_file_path or not os.path.exists(task.template_file_path):
        return {"skipped": True, "reason": "no template file on disk for this task"}

    existing_column_rules = json.loads(task.column_rules) if task.column_rules else []
    result = _extract_and_merge_excel_rules(task.template_file_path, existing_column_rules)

    if result["rules_changed"]:
        task.column_rules = json.dumps(result["column_rules"])

    _merge_excel_metadata(task, result)

    return {
        "skipped": False,
        "validation_rules_found": result["validation_rules_found"],
        "formula_rules_found": result["formula_rules_found"],
        "inferred_formula_rules_found": result["inferred_formula_rules_found"],
        "advisory_notes_found": len(result["advisory_notes"]),
        "has_vba_source": bool(result["vba_text"]),
        "vba_business_rules_found": len(result["vba_business_rules"]),
    }


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

    validation_report = None
    if isinstance(category_metadata, dict):
        validation_report = category_metadata.get("validation_report")

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
        "validation_report": validation_report,
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
    still list, view, and run existing tasks; creating, editing, and
    deleting tasks is restricted to admins.
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

    # Get column rules from the target table if provided, otherwise — for
    # report_analyses — infer them straight from the uploaded Excel
    # template, the same way a skill_engine task gets its rules from a
    # parsed rules document at creation time. Parsed once here and reused
    # on every future upload, instead of the template being nothing more
    # than a column-header reference.
    column_rules = None
    target_table_clean = target_table.strip() or None
    if target_table_clean:
        column_rules = get_table_column_rules(engine, target_table_clean)
    elif category == "report_analyses" and template_file_path:
        column_rules = infer_column_rules(
            json.loads(expected_columns) if expected_columns else [],
            read_data_rows(template_file_path),
        )

    # Mine the template's own formulas, data validation, conditional
    # formatting, and (for .xlsm) VBA macros for additional business
    # rules — see excel_rule_parser.py — plus any cross-column
    # relationship (e.g. Total = Qty * Price) that holds across every
    # sample row even without a live formula behind it (see
    # validation_service.infer_formula_rules). Data validation and
    # formula rules (structural or inferred) are enforced like any
    # other column_rule; conditional formatting and VBA are advisory.
    excel_result = None
    if category == "report_analyses" and template_file_path:
        excel_result = _extract_and_merge_excel_rules(template_file_path, column_rules)
        column_rules = excel_result["column_rules"]

    # Parse category_metadata if provided
    parsed_category_metadata = None
    if category_metadata and category_metadata != "null":
        try:
            parsed_category_metadata = json.loads(category_metadata)
        except (json.JSONDecodeError, TypeError, ValueError):
            parsed_category_metadata = None

    if excel_result and (
        excel_result["advisory_notes"] or excel_result["vba_text"] or excel_result["vba_business_rules"]
    ):
        parsed_category_metadata = parsed_category_metadata or {}
        if excel_result["advisory_notes"]:
            parsed_category_metadata["excel_advisory_notes"] = excel_result["advisory_notes"]
        if excel_result["vba_text"]:
            parsed_category_metadata["excel_vba_text"] = excel_result["vba_text"]
        if excel_result["vba_business_rules"]:
            # Advisory, like the VBA source it comes from: not
            # auto-enforced (VBA is arbitrary code, not a structural
            # artifact), but stored for an admin to review.
            parsed_category_metadata["excel_vba_business_rules"] = excel_result["vba_business_rules"]

    if excel_result and excel_result["vba_text"]:
        # Kept as reference text for the AI assistant alongside the
        # rules document, if any — the interpreted business-logic
        # rules above are what's actually reviewable/usable, this is
        # just the raw source they were read from.
        rules_text = (
            (rules_text + "\n\n" if rules_text else "")
            + "=== VBA MACRO SOURCE (extracted from the uploaded Excel "
            "template; may encode additional business rules) ===\n"
            + excel_result["vba_text"]
        )
        rules_content = json.dumps({"full_text": rules_text})

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
    current_user: User = Depends(get_current_admin_user),
):
    """
    Update an existing configuration task. Admin only.
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
    rules_text = None
    excel_result = None
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
            # Re-infer column rules from the new template, unless a
            # target_table drives them instead (handled above).
            if not task.target_table:
                task.column_rules = json.dumps(
                    infer_column_rules(
                        json.loads(task.expected_columns),
                        read_data_rows(saved_path),
                    )
                )
        else:
            task.expected_columns = "[]"

        # Mine the new template's own formulas, data validation,
        # conditional formatting, VBA macros, and any cross-column
        # relationship that holds across every sample row even without
        # a live formula — see _extract_and_merge_excel_rules. Runs
        # regardless of whether column_rules came from a target_table
        # or from infer_column_rules just above.
        if effective_category == "report_analyses":
            existing_column_rules = json.loads(task.column_rules) if task.column_rules else []
            excel_result = _extract_and_merge_excel_rules(saved_path, existing_column_rules)
            task.column_rules = json.dumps(excel_result["column_rules"])

    # ✅ Update rules document if provided
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

    if excel_result:
        _merge_excel_metadata(task, excel_result)

        if excel_result["vba_text"]:
            # Reference text for the AI assistant alongside the rules
            # document, if any — appended, not fed into
            # _store_rules_with_examples below: that call overwrites
            # parsed_rules wholesale, so doing it with only the macro
            # source (no rules_file this call) would silently wipe out
            # rules parsed from an earlier, unrelated rules document.
            # The macro source's own business-logic rules are already
            # captured separately (excel_vba_business_rules, set by
            # _merge_excel_metadata above); this is just its raw text.
            full_text = (
                (rules_text + "\n\n" if rules_text else "")
                + "=== VBA MACRO SOURCE (extracted from the uploaded Excel "
                "template; may encode additional business rules) ===\n"
                + excel_result["vba_text"]
            )
            task.rules_content = json.dumps({"full_text": full_text})

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
    current_user: User = Depends(get_current_admin_user),
):
    """
    Delete a configuration task by ID (soft delete). Admin only.
    """
    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == task_id).first()

    if not task:
        return {"message": "Task already deleted", "success": True}

    # Soft delete - mark as inactive
    task.is_active = False
    db.commit()

    return {"message": f"Task '{task.name}' deleted successfully", "success": True}


@router.post("/{task_id}/rescan-excel-rules")
def rescan_task_excel_rules(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Re-reads a report_analyses task's stored template file for
    formulas, data validation, conditional formatting, and VBA, and
    merges anything found into the task's column_rules /
    category_metadata. Admin only.

    For a task created before excel_rule_parser existed (or whose
    template was never re-uploaded since), this is how it picks up the
    new rules without an admin having to re-upload the same file.
    Safe to call more than once — merging is idempotent.
    """
    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    result = _rescan_excel_rules_for_task(task)

    if not result["skipped"]:
        db.commit()
        db.refresh(task)

    return {"task_id": task.id, "task_name": task.name, **result}


@router.post("/rescan-excel-rules")
def rescan_all_excel_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Bulk version of rescan_task_excel_rules: re-scans every active
    report_analyses task's template file in one pass. Admin only.

    One-time backfill for tasks created before excel_rule_parser
    existed, and safe to re-run any time after (e.g. after improving
    the extractor itself) since merging is idempotent.
    """
    tasks = (
        db.query(ConfigurationTask)
        .filter(ConfigurationTask.is_active == True, ConfigurationTask.category == "report_analyses")
        .all()
    )

    results = []
    for task in tasks:
        result = _rescan_excel_rules_for_task(task)
        results.append({"task_id": task.id, "task_name": task.name, **result})

    db.commit()

    return {
        "scanned": len(results),
        "updated": sum(1 for r in results if not r["skipped"]),
        "results": results,
    }


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
