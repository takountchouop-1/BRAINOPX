import os
import json
import logging
import math
import uuid
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime

from ..db.database import get_db
from ..db.models import ConfigurationTask, ConfigurationRequest, ReportReferenceFile, ReportScriptVersion, StepAttachment, User
from ..db.deps import get_current_user
from ..services.excel_service import extract_column_headers, read_data_rows
from ..services.validation_service import validate_data_rows, infer_column_rules
from ..services import validation_service
from ..services.template_matcher import auto_match_template, get_all_templates, get_match_summary
from ..services.groq_service import (
    get_ai_response,
    get_rule_aware_response,
    run_rule_workflow,
    parse_rules_to_json,
    generate_workflow_script,
    build_no_template_welcome_message,
    GroqNetworkError,
)
from ..services.notification_service import create_notification
from ..services.rule_parser import extract_text
from ..services.skill_engine_service import (
    get_rules_for_task,
    evaluate_input_against_rules,
    build_rules_summary_message,
)
from ..services.step_by_step_service import (
    init_workflow as init_step_workflow,
    get_step_initial_message,
    process_step_input,
    get_workflow_progress,
    list_completed_steps,
    edit_step,
    regenerate_current_example,
    submit_step_attachment,
)
from ..services import report_analysis_service

router = APIRouter(prefix="/api/requests", tags=["requests"])

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join("uploads", "requests")
os.makedirs(UPLOAD_DIR, exist_ok=True)

STEP_ATTACHMENT_DIR = os.path.join("uploads", "requests", "step_attachments")
os.makedirs(STEP_ATTACHMENT_DIR, exist_ok=True)

STEP_ATTACHMENT_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
STEP_ATTACHMENT_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".csv"}
ALLOWED_STEP_ATTACHMENT_EXTENSIONS = STEP_ATTACHMENT_IMAGE_EXTENSIONS | STEP_ATTACHMENT_DOCUMENT_EXTENSIONS
MAX_STEP_ATTACHMENT_SIZE = 15 * 1024 * 1024  # 15MB


def _json_safe(value):
    """
    Recursively replaces any NaN/Infinity float (e.g. from a raw_rows
    blob saved before _sanitize_row existed) with None, so an
    already-corrupted stored request self-heals on read instead of
    permanently 500ing GET /{request_id}.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _sanitize_row(row_data: dict) -> dict:
    """
    pandas represents a blank Excel cell as float('nan') even under
    dtype=str (the dtype hint only casts non-null values). NaN survives
    json.dumps() fine, but Starlette's JSONResponse rejects it outright
    (ValueError: Out of range float values are not JSON compliant), which
    crashed GET /{request_id} for any request whose analysis_state ended
    up storing one of these rows. Blank cells become None here instead,
    the same way excel_service.read_data_rows()'s openpyxl-based reader
    already represents them.
    """
    return {
        key: (None if isinstance(value, float) and pd.isna(value) else value)
        for key, value in row_data.items()
    }


def _file_url(path: str | None) -> str | None:
    """
    Turns a stored file path (e.g. "uploads\\requests\\xxx.xlsx") into
    the URL it's served at — main.py mounts the "uploads" directory at
    /uploads — so the frontend can open/download the original file
    directly (e.g. to fix a flagged cell in Excel and resubmit it).
    """
    if not path:
        return None
    normalized = path.replace("\\", "/").lstrip("/")
    return f"/{normalized}"


def _rules_text_of(task) -> str:
    """
    task.rules_content is sometimes a raw string, sometimes a JSON blob
    of the form {"full_text": "..."} — same unwrapping as the
    fallback branch of step_chat_with_assistant's sibling AI call.
    """
    if not task or not task.rules_content:
        return ""
    try:
        obj = json.loads(task.rules_content)
        return obj.get("full_text", "") or ""
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return task.rules_content or ""


def _structural_welcome_message(
    task_name: str,
    match_score: float,
    match_summary: dict,
    validation_errors: list,
) -> str:
    """
    Fallback AI message for a report_analyses task with no per-rule or
    per-column engine to run (no rules_context, no column_rules — e.g.
    the task was created without a target table). Without this, the
    chat panel is left completely empty after upload even though the
    file was received and column-matched, which reads as "nothing
    happened". Built entirely from data already computed on upload, so
    it needs no extra AI call.
    """
    matched = sorted(match_summary.get("matched_columns") or [])
    missing = sorted(match_summary.get("missing_columns") or [])
    extra = sorted(match_summary.get("extra_columns") or [])

    lines = [f"Thanks for the upload! I've matched your file to **'{task_name}'** ({match_score}% match)."]
    if matched:
        lines.append(f"- **Matched columns:** {', '.join(matched)}")
    if missing:
        lines.append(f"- **Missing columns:** {', '.join(missing)} — could you add them and upload the file again?")
    if extra:
        lines.append(f"- **Extra columns not expected by this task:** {', '.join(extra)} — no worries, I'll just ignore those.")
    if validation_errors:
        lines.append(
            f"- **Row-level issues found:** {len(validation_errors)} — nothing we can't sort out together, "
            "take a look at the Validation Report below and we'll go through them one by one."
        )
    if not missing and not validation_errors:
        lines.append("Great news — your file looks structurally correct against this task's expected columns.")

    return "\n\n".join(lines)


def _infer_and_persist_column_rules(db: Session, task: ConfigurationTask) -> list:
    """
    Self-heals a report_analyses task created before column-rule
    inference existed (no target_table, no column_rules): infers a rule
    set from the task's own Excel template — the same source a
    newly-created task now gets its rules from — and persists it so
    this only has to run once per task, not on every upload.
    """
    if not task.template_file_path or not os.path.exists(task.template_file_path):
        return []

    try:
        headers = extract_column_headers(task.template_file_path)
        template_rows = read_data_rows(task.template_file_path)
    except HTTPException:
        return []

    inferred = infer_column_rules(headers, template_rows)
    if inferred:
        task.column_rules = json.dumps(inferred)
        db.commit()

    return inferred


_REFERENCE_FILE_QUESTIONS = {
    "missing_value": "Row {row}, column '{column}' is missing a value. Could you send the correct value, or upload a production extract that has it?",
    "invalid_format": "Row {row}, column '{column}' has a value in the wrong format. Could you send a corrected value, or upload a production extract that has it?",
    "duplicate": "Row {row}, column '{column}' duplicates a value used elsewhere in the file. Could you send the correct value?",
    "negative_value": "Row {row}, column '{column}' has a negative value, which doesn't look right for this field. Could you send the correct value?",
    "unknown_code": "I couldn't find code '{code}' (row {row}, column '{column}') in the database. Could you upload a production extract so I can cross-check it?",
    "inconsistent_value": "Row {row}, column '{column}' disagrees with another row describing the same record. Could you tell me which value is correct?",
    "incomplete_relationship": "Row {row}, column '{column}' references a database record that is itself missing required data. Could you upload a production extract with the complete record?",
    "duplicate_row": "Row {row} looks like a duplicate of another row — same values across every column. Could you confirm whether this is intentional, or tell me the correct value(s)?",
    "invalid_choice": "Row {row}, column '{column}' isn't one of the template's allowed choices. Could you send the correct value?",
    "out_of_range": "Row {row}, column '{column}' is outside the range the template allows. Could you send the correct value?",
    "invalid_length": "Row {row}, column '{column}' has the wrong length for the template's rule. Could you send the correct value?",
    "formula_mismatch": "Row {row}, column '{column}' doesn't match the template's own formula. Could you send the correct value?",
}


def _run_report_analysis_check(
    db: Session,
    request: ConfigurationRequest,
    task: ConfigurationTask,
    data_rows: list[dict],
    validation_errors: list[dict],
) -> None:
    """
    Full anomaly scan for report_analyses tasks (see
    report_analysis_service.py): unknown FK codes, missing values,
    invalid formats, duplicates, inconsistent values, and incomplete
    relationships all get seeded as anomalies that can be resolved
    through the same correction / reference-file / decision actions.

    Mutates validation_errors in place (each entry gets an
    anomaly_id) — the caller must re-persist it after this returns.

    Appends one grouped summary to the conversation and advances
    current_stage/status so the request shows as needing more input,
    without touching the step-by-step / rule-engine flows above this
    call.
    """

    if not task.column_rules:
        logger.warning(
            "report_analyses task %s (%s) has no column_rules — skipping anomaly scan; "
            "the file was only checked for column-header matches.",
            task.id, task.name,
        )
        return

    try:
        column_rules = json.loads(task.column_rules)
    except (json.JSONDecodeError, TypeError, ValueError):
        return

    state = report_analysis_service.run_full_anomaly_scan(
        db, request, data_rows, column_rules, validation_errors, task_type=task.category,
    )

    # Always runs, even with zero anomalies — build_anomaly_summary_message
    # and sync_stage_from_state both handle that case correctly (a
    # friendly "all clear" message and advancing to "validated"), and
    # skipping them here would leave a resubmitted, now-clean file stuck
    # at its old status.
    pending = report_analysis_service.pending_reference_requests(request)
    for anomaly in pending:
        template = _REFERENCE_FILE_QUESTIONS.get(anomaly["kind"], _REFERENCE_FILE_QUESTIONS["unknown_code"])
        question = template.format(
            row=anomaly.get("row"), column=anomaly.get("column"), code=anomaly.get("code"),
        )
        report_analysis_service.record_question_asked(db, request, anomaly["id"], question)

    conversation = []
    if request.conversation:
        try:
            conversation = json.loads(request.conversation)
        except (json.JSONDecodeError, TypeError, ValueError):
            conversation = []

    conversation.append({
        "sender": "ai",
        "text": report_analysis_service.build_anomaly_summary_message(state),
        "timestamp": datetime.now().isoformat(),
    })
    request.conversation = json.dumps(conversation)
    db.add(request)
    db.commit()

    report_analysis_service.sync_stage_from_state(db, request, state)


@router.get("/task-welcome/{task_id}")
def get_task_welcome(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    When a user selects a task from the dropdown, the AI responds instantly
    with a welcome message introducing the task's rules and guiding the user.

    IMPORTANT: If the task has rules, a draft ConfigurationRequest is created
    automatically and the step-by-step workflow is initialised so the user can
    start chatting about the FIRST rule immediately — no file upload required.
    """
    task = db.query(ConfigurationTask).filter(
        ConfigurationTask.id == task_id,
        ConfigurationTask.is_active == True
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task template not found."
        )

    # Get the rules associated with this task
    rules = get_rules_for_task(db, task.id)

    request_id = None
    step_progress = None
    conversation = []

    if rules:
        # Build the welcome message
        rules_list = "\n".join([
            "  " + str(i+1) + ". **" + str(r.get('name', 'Rule ' + str(i+1))) + "** — " + str(r.get('task', r.get('description', '')))[:120]
            for i, r in enumerate(rules)
        ])
        welcome_message = (
            "**Welcome!** You've selected the task **'" + task.name + "'**.\n\n"
            "This task has **" + str(len(rules)) + " rules** that need to be satisfied:\n\n"
            + rules_list + "\n\n"
            + "**Let's get started!**\n"
            + "I'll guide you through each rule one at a time. "
            + "Please respond to the first step below.\n\n"
            + "*(You can also upload an Excel file later if you have one.)*"
        )

        # Create a draft request so the user can chat immediately
        new_request = ConfigurationRequest(
            task_id=task.id,
            user_id=current_user.id,
            status="file_submitted",
            uploaded_filename=None,
            uploaded_file_path=None,
            validation_errors=None,
            eval_profile=None,
            conversation=json.dumps([{
                "sender": "ai",
                "text": welcome_message,
                "timestamp": datetime.now().isoformat(),
            }]),
        )
        db.add(new_request)
        db.commit()
        db.refresh(new_request)
        request_id = new_request.id

        # Initialise the step-by-step workflow
        try:
            workflow = init_step_workflow(new_request, db, rules)
            initial_step_message = get_step_initial_message(new_request, db)
            step_progress = get_workflow_progress(new_request)

            # Update conversation with the step-by-step initial message
            conversation = []
            if initial_step_message:
                conversation.append({
                    "sender": "ai",
                    "text": initial_step_message,
                    "timestamp": datetime.now().isoformat(),
                })
            new_request.conversation = json.dumps(conversation)
            db.commit()
        except Exception:
            # If workflow init fails, keep the welcome message as conversation
            conversation = []
            if new_request.conversation:
                try:
                    conversation = json.loads(new_request.conversation)
                except (json.JSONDecodeError, TypeError, ValueError):
                    conversation = []
    else:
        welcome_message = (
            "**Welcome!** You've selected the task **'" + task.name + "'**.\n\n"
            + "This task doesn't have any specific rules defined. Upload your Excel "
            + "configuration file and I'll help validate it."
        )

    return {
        "task_id": task.id,
        "task_name": task.name,
        "rules": rules,
        "welcome_message": welcome_message,
        "request_id": request_id,
        "step_progress": step_progress,
        "conversation": conversation,
    }


def _open_no_template_request(
    db: Session,
    current_user: User,
    saved_path: str,
    filename: str,
    match_score: float = 0.0,
) -> dict:
    """
    Open a configuration request with no task attached (task_id NULL) for
    a file that has no task template. The AI assistant takes over the
    conversation to ask what the task should be — and can escalate to an
    expert from there. Shared by /upload (no templates at all) and
    /upload-without-template (user decided none of the existing templates
    fit).
    """

    uploaded_columns = extract_column_headers(saved_path)
    language = getattr(current_user, "language", "en") or "en"
    welcome = build_no_template_welcome_message(
        uploaded_columns, filename, language
    )
    conversation = [{
        "sender": "ai",
        "text": welcome,
        "timestamp": datetime.now().isoformat(),
    }]

    new_request = ConfigurationRequest(
        task_id=None,
        user_id=current_user.id,
        status="additional_information_required",
        uploaded_filename=filename,
        uploaded_file_path=saved_path,
        validation_errors=None,
        eval_profile=None,
        conversation=json.dumps(conversation),
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    return {
        "id": new_request.id,
        "task_id": None,
        "task_name": None,
        "status": new_request.status,
        "current_stage": new_request.current_stage,
        "validation_errors": [],
        "rule_results": [],
        "ai_welcome_message": welcome,
        "conversation": conversation,
        "step_progress": None,
        "match_score": match_score,
        "match_summary": None,
        "no_template": True,
        "uploaded_file": filename,
        "file_url": _file_url(saved_path),
    }


@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an Excel file for configuration.
    Auto-matches the file to a task template based on column headers.
    """
    # Validate file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".xlsx", ".xls", ".csv"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx, .xls, or .csv files are supported."
        )
    
    # Save the uploaded file
    unique_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, unique_name)
    
    with open(saved_path, "wb") as buffer:
        buffer.write(file.file.read())
    
    # Auto-match template
    matched_task, match_score = auto_match_template(saved_path, db)
    
    # Get all templates for fallback
    all_templates = get_all_templates(db)
    
    # No confident auto-match, but templates do exist — let the user pick
    # the right one by hand instead of guessing.
    if not matched_task and all_templates:
        return {
            "error": "No matching template found",
            "match_score": match_score,
            "available_templates": all_templates,
            "uploaded_file": file.filename,
            "uploaded_file_path": saved_path,
            "requires_manual_selection": True
        }
    
    # No task template exists in the database at all. Don't dead-end the
    # user: open a configuration request with no task attached and let the
    # AI assistant ask what the task should be (and, if asked, escalate to
    # an expert). The same conversation then continues when they come back.
    if not matched_task:
        return _open_no_template_request(
            db,
            current_user,
            saved_path,
            file.filename,
            match_score,
        )
    
    # Extract data rows from the file
    df = pd.read_excel(saved_path, dtype=str)
    data_rows = []
    for idx, row in df.iterrows():
        row_data = _sanitize_row(row.to_dict())
        row_data["_row_number"] = idx + 2  # Excel row number (1-indexed, skipping header)
        data_rows.append(row_data)
    
    # Run validation using the matched task's column rules — falling back
    # to a rule set inferred from the uploaded file's own data when the
    # task has no target_table configured (no DB-derived column_rules),
    # so the file still gets real per-row validation instead of only a
    # column-header match.
    validation_errors = []
    if matched_task.column_rules:
        column_rules = json.loads(matched_task.column_rules) if matched_task.column_rules else []
        validation_errors = validate_data_rows(db, data_rows, column_rules)
    elif matched_task.category == "report_analyses":
        inferred_rules = _infer_and_persist_column_rules(db, matched_task)
        if inferred_rules:
            validation_errors = validate_data_rows(db, data_rows, inferred_rules)
    
    # Run the rule engine — evaluate the uploaded file against the task's rules.
    # Each rule triggers its own AI workflow; the AI responds instantly based on
    # the rules that were uploaded when the task was created.
    rule_results = []
    rules_context = get_rules_for_task(db, matched_task.id)
    ai_welcome_message = None

    if rules_context:
        try:
            # Extract text from the uploaded file to feed the rule workflows
            file_text = extract_text(saved_path)
            rules_context, rule_results = evaluate_input_against_rules(db, matched_task.id, file_text)
            ai_welcome_message = build_rules_summary_message(
                matched_task.name,
                rules_context,
                rule_results,
            )
        except GroqNetworkError:
            rule_results = []
            ai_welcome_message = "Please check your network and retry."
        except Exception as e:
            # If rule evaluation fails, don't block the upload
            rule_results = []
            ai_welcome_message = (
                f"Your file has been received for task **'{matched_task.name}'**. "
                "I wasn't able to analyse it against the rules automatically. "
                "Please tell me what you'd like to achieve and I'll guide you."
            )

    # Get match summary — computed early so the fallback welcome message
    # below (for tasks with no per-rule/column engine, e.g. a
    # report_analyses task created without a target table) can describe
    # what it found instead of leaving the chat panel empty.
    uploaded_columns = extract_column_headers(saved_path)
    expected_columns = json.loads(matched_task.expected_columns) if matched_task.expected_columns else []
    match_summary = get_match_summary(uploaded_columns, expected_columns)

    if not ai_welcome_message:
        ai_welcome_message = _structural_welcome_message(
            matched_task.name, match_score, match_summary, validation_errors
        )

    # Initial conversation: seed with the AI's instant rule-aware response
    conversation = []
    if ai_welcome_message:
        conversation.append({
            "sender": "ai",
            "text": ai_welcome_message,
            "timestamp": datetime.now().isoformat(),
        })

    # No rules_context means there's no step-by-step workflow to walk the
    # user through (that's the only thing gated on rules_context below) —
    # whether or not column_rules validation ran, the request has nothing
    # left to do, so reflect the analysis outcome right away instead of
    # leaving it stuck at "file_submitted" forever.
    initial_status = "file_submitted"
    if not rules_context:
        initial_status = (
            "additional_information_required"
            if (match_summary["missing_columns"] or validation_errors)
            else "data_validated"
        )

# Create the configuration request
    new_request = ConfigurationRequest(
        task_id=matched_task.id,
        user_id=current_user.id,
        status=initial_status,
        uploaded_filename=file.filename,
        uploaded_file_path=saved_path,
        validation_errors=json.dumps(validation_errors),
        eval_profile=json.dumps({"rule_results": rule_results}) if rule_results else None,
        conversation=json.dumps(conversation),
    )
    
    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    # Full anomaly scan — no-op if the task has no column_rules at all.
    # Mutates validation_errors in place (stamps anomaly_id onto each
    # entry), so it must be re-persisted afterward.
    _run_report_analysis_check(db, new_request, matched_task, data_rows, validation_errors)
    new_request.validation_errors = json.dumps(validation_errors)
    db.commit()

    # ── STEP-BY-STEP WORKFLOW INIT ──────────────────────────────────
    # If the task has rules, initialise the step-by-step workflow so the
    # AI guides the user through each rule one at a time.
    step_progress = None
    initial_step_message = None
    if rules_context:
        try:
            workflow = init_step_workflow(new_request, db, rules_context)
            initial_step_message = get_step_initial_message(new_request, db)
            step_progress = get_workflow_progress(new_request)

            # Update the conversation with the step-by-step initial message
            conversation = []
            if initial_step_message:
                conversation.append({
                    "sender": "ai",
                    "text": initial_step_message,
                    "timestamp": datetime.now().isoformat(),
                })
            new_request.conversation = json.dumps(conversation)
            db.commit()
        except Exception:
            # If workflow init fails, fall back to the existing conversation
            pass

    # Re-sync from the DB: _run_report_analysis_check (and/or the
    # step-by-step init above) may have appended to new_request.conversation
    # since the local `conversation` variable was last built.
    try:
        conversation = json.loads(new_request.conversation) if new_request.conversation else []
    except (json.JSONDecodeError, TypeError, ValueError):
        conversation = []

    return {
        "id": new_request.id,
        "task_id": matched_task.id,
        "task_name": matched_task.name,
        "status": new_request.status,
        "current_stage": new_request.current_stage,
        "validation_errors": validation_errors,
        "rule_results": rule_results,
        "ai_welcome_message": ai_welcome_message,
        "conversation": conversation,
        "step_progress": step_progress,
        "match_score": match_score,
        "match_summary": match_summary,
        "uploaded_file": file.filename,
        "file_url": _file_url(saved_path),
    }


@router.post("/upload-without-template")
def upload_file_without_template(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an Excel file that the user says matches none of the existing
    task templates. Opens a no-template request so the AI assistant can
    still analyse the file and help define the missing task (and, if
    asked, escalate to an expert) — the same fallback /upload uses when
    there are no templates at all.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".xlsx", ".xls", ".csv"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx, .xls, or .csv files are supported.",
        )

    unique_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(saved_path, "wb") as buffer:
        buffer.write(file.file.read())

    return _open_no_template_request(
        db,
        current_user,
        saved_path,
        file.filename,
    )


@router.post("/upload-with-template")
def upload_file_with_template(
    file: UploadFile = File(...),
    task_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an Excel file with a manually selected template.
    This is the fallback when auto-match fails.
    """
    # Validate file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".xlsx", ".xls", ".csv"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx, .xls, or .csv files are supported."
        )
    
    # Get the selected task
    task = db.query(ConfigurationTask).filter(
        ConfigurationTask.id == task_id,
        ConfigurationTask.is_active == True
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task template not found."
        )
    
    # Save the uploaded file
    unique_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, unique_name)
    
    with open(saved_path, "wb") as buffer:
        buffer.write(file.file.read())
    
    # Extract data rows
    df = pd.read_excel(saved_path, dtype=str)
    data_rows = []
    for idx, row in df.iterrows():
        row_data = _sanitize_row(row.to_dict())
        row_data["_row_number"] = idx + 2
        data_rows.append(row_data)
    
    # Run validation — same fallback as /upload: infer rules from the
    # file's own data when the task has no target_table configured.
    validation_errors = []
    if task.column_rules:
        column_rules = json.loads(task.column_rules) if task.column_rules else []
        validation_errors = validate_data_rows(db, data_rows, column_rules)
    elif task.category == "report_analyses":
        inferred_rules = _infer_and_persist_column_rules(db, task)
        if inferred_rules:
            validation_errors = validate_data_rows(db, data_rows, inferred_rules)
    
    # Run the rule engine — evaluate the uploaded file against the task's rules.
    rule_results = []
    rules_context = get_rules_for_task(db, task.id)
    ai_welcome_message = None

    if rules_context:
        try:
            file_text = extract_text(saved_path)
            rules_context, rule_results = evaluate_input_against_rules(db, task.id, file_text)
            ai_welcome_message = build_rules_summary_message(
                task.name,
                rules_context,
                rule_results,
            )
        except GroqNetworkError:
            rule_results = []
            ai_welcome_message = "Please check your network and retry."
        except Exception:
            rule_results = []
            ai_welcome_message = (
                f"Your file has been received for task **'{task.name}'**. "
                "I wasn't able to analyse it against the rules automatically. "
                "Please tell me what you'd like to achieve and I'll guide you."
            )

    # Match summary — no auto-match score here (the user picked the
    # template directly), but the column comparison is still useful, and
    # feeds the fallback welcome message below just like /upload.
    uploaded_columns = extract_column_headers(saved_path)
    expected_columns = json.loads(task.expected_columns) if task.expected_columns else []
    match_summary = get_match_summary(uploaded_columns, expected_columns)

    if not ai_welcome_message:
        ai_welcome_message = _structural_welcome_message(
            task.name, 100.0, match_summary, validation_errors
        )

    conversation = []
    if ai_welcome_message:
        conversation.append({
            "sender": "ai",
            "text": ai_welcome_message,
            "timestamp": datetime.now().isoformat(),
        })

    initial_status = "file_submitted"
    if not rules_context:
        initial_status = (
            "additional_information_required"
            if (match_summary["missing_columns"] or validation_errors)
            else "data_validated"
        )

    # Create the configuration request
    new_request = ConfigurationRequest(
        task_id=task.id,
        user_id=current_user.id,
        status=initial_status,
        uploaded_filename=file.filename,
        uploaded_file_path=saved_path,
        validation_errors=json.dumps(validation_errors),
        eval_profile=json.dumps({"rule_results": rule_results}) if rule_results else None,
        conversation=json.dumps(conversation),
    )
    
    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    # Full anomaly scan — no-op if the task has no column_rules at all.
    # Mutates validation_errors in place (stamps anomaly_id onto each
    # entry), so it must be re-persisted afterward.
    _run_report_analysis_check(db, new_request, task, data_rows, validation_errors)
    new_request.validation_errors = json.dumps(validation_errors)
    db.commit()

    # ── STEP-BY-STEP WORKFLOW INIT ──────────────────────────────────
    # Mirrors /upload: if the task has rules, initialise the step-by-step
    # workflow so the AI guides the user through each rule one at a time,
    # regardless of whether the template was auto-matched or hand-picked.
    step_progress = None
    if rules_context:
        try:
            init_step_workflow(new_request, db, rules_context)
            initial_step_message = get_step_initial_message(new_request, db)
            step_progress = get_workflow_progress(new_request)

            conversation = []
            if initial_step_message:
                conversation.append({
                    "sender": "ai",
                    "text": initial_step_message,
                    "timestamp": datetime.now().isoformat(),
                })
            new_request.conversation = json.dumps(conversation)
            db.commit()
        except Exception:
            # If workflow init fails, fall back to the existing conversation
            pass

    # Re-sync from the DB: _run_report_analysis_check (and/or the
    # step-by-step init above) may have appended to new_request.conversation
    # since the local `conversation` variable was last built.
    try:
        conversation = json.loads(new_request.conversation) if new_request.conversation else []
    except (json.JSONDecodeError, TypeError, ValueError):
        conversation = []

    return {
        "id": new_request.id,
        "task_id": task.id,
        "task_name": task.name,
        "status": new_request.status,
        "current_stage": new_request.current_stage,
        "validation_errors": validation_errors,
        "rule_results": rule_results,
        "ai_welcome_message": ai_welcome_message,
        "conversation": conversation,
        "step_progress": step_progress,
        "match_summary": match_summary,
        "uploaded_file": file.filename,
        "file_url": _file_url(saved_path),
    }


@router.post("/{request_id}/resubmit-file")
def resubmit_corrected_file(
    request_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Swap in a corrected version of the uploaded file — the "open it in
    Excel, fix the flagged cells, send it back" loop: the user
    downloads the file via this request's file_url, corrects it
    locally, and resubmits it here instead of typing each correction
    into the chat. Re-runs the same validation/anomaly scan /upload
    and /upload-with-template run on first upload, against this same
    request (not a new one), so the conversation and any
    already-resolved anomalies carry forward.
    """
    request = _get_request_or_404(db, request_id)

    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".xlsx", ".xls", ".csv"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx, .xls, or .csv files are supported.",
        )

    unique_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(saved_path, "wb") as buffer:
        buffer.write(file.file.read())

    df = pd.read_excel(saved_path, dtype=str)
    data_rows = []
    for idx, row in df.iterrows():
        row_data = _sanitize_row(row.to_dict())
        row_data["_row_number"] = idx + 2
        data_rows.append(row_data)

    validation_errors = []
    if task.column_rules:
        column_rules = json.loads(task.column_rules)
        validation_errors = validate_data_rows(db, data_rows, column_rules)
    elif task.category == "report_analyses":
        inferred_rules = _infer_and_persist_column_rules(db, task)
        if inferred_rules:
            validation_errors = validate_data_rows(db, data_rows, inferred_rules)

    old_path = request.uploaded_file_path
    request.uploaded_filename = file.filename
    request.uploaded_file_path = saved_path
    request.validation_errors = json.dumps(validation_errors)
    db.commit()
    _remove_uploaded_file(old_path)

    conversation = []
    if request.conversation:
        try:
            conversation = json.loads(request.conversation)
        except (json.JSONDecodeError, TypeError, ValueError):
            conversation = []
    conversation.append({
        "sender": "ai",
        "text": "Thanks for sending that back! Let me take another look at your corrected file.",
        "timestamp": datetime.now().isoformat(),
    })
    request.conversation = json.dumps(conversation)
    db.commit()

    # Mutates validation_errors in place (anomaly_id stamped on each
    # entry) and appends its own summary turn to the conversation.
    _run_report_analysis_check(db, request, task, data_rows, validation_errors)
    request.validation_errors = json.dumps(validation_errors)
    db.commit()

    conversation = json.loads(request.conversation) if request.conversation else []

    return {
        "request_id": request_id,
        "uploaded_file": file.filename,
        "file_url": _file_url(saved_path),
        "status": request.status,
        "current_stage": request.current_stage,
        "validation_errors": validation_errors,
        "conversation": conversation,
        "all_resolved": report_analysis_service.all_resolved(request),
    }


@router.get("/{request_id}/step-progress")
def get_step_progress(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the step-by-step workflow progress for a request.
    """
    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found."
        )
    
    progress = get_workflow_progress(request)
    return progress if progress else {"total_steps": 0, "completed_steps": 0, "all_completed": False}
    

@router.post("/{request_id}/step-chat")
def step_chat_with_assistant(
    request_id: int,
    message: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to the step-by-step AI assistant for a specific request.
    Each message is processed against the current step (rule) in the workflow.
    """
    # Get the request
    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found."
        )
    
    # Process the input through the step-by-step workflow
    result = process_step_input(request, db, message)
    
    # Get conversation history
    conversation_history = []
    if request.conversation:
        try:
            conversation_history = json.loads(request.conversation)
        except:
            conversation_history = []
    
    # Save conversation
    # `validated` is stored with the message so the confirmation on the
    # user's bubble survives a reload. The client rebuilds the chat from
    # this history, which would otherwise drop the outcome.
    conversation_history.append({
        "sender": "user",
        "text": message,
        "validated": bool(result.get("passed", False)),
        "timestamp": datetime.now().isoformat()
    })
    conversation_history.append({
        "sender": "ai",
        "text": result.get("ai_response", ""),
        "passed": bool(result.get("passed", False)),
        "timestamp": datetime.now().isoformat()
    })
    
    request.conversation = json.dumps(conversation_history)
    db.commit()
    
    # Finishing the walkthrough *is* finishing the request for this
    # workflow — there is no further script-generation step waiting
    # for it, so leaving it at "data_validated" (as before) meant it
    # never left the "pending" bucket on the dashboard/graph until
    # someone separately clicked "Mark complete". Complete it here
    # instead, so the dashboard summary and Graph Analysis tab pick it
    # up as soon as the last step is answered.
    if result.get("all_completed", False):
        request.status = "processing_completed"
        db.commit()

        # The user's answers are the whole point of the walkthrough —
        # synthesize the script they describe right away rather than
        # making completion a dead end the user has to separately
        # trigger a script for.
        try:
            task = db.query(ConfigurationTask).filter(
                ConfigurationTask.id == request.task_id
            ).first()
            request.generated_script = generate_workflow_script(
                task_name=task.name if task else "",
                task_description=task.description if task else "",
                rules_content=_rules_text_of(task),
                completed_steps=list_completed_steps(request),
                language=getattr(current_user, "language", "en") or "en",
            )
            db.commit()
        except Exception:
            logger.exception(
                "Script generation failed for request %s; leaving it completed without one.",
                request_id,
            )

    return {
        "request_id": request_id,
        "user_message": message,
        "ai_response": result.get("ai_response", ""),
        "step_index": result.get("step_index", 0),
        "step_name": result.get("step_name", ""),
        "status": result.get("status", ""),
        "passed": result.get("passed", False),
        "all_completed": result.get("all_completed", False),
        "progress": result.get("progress", None),
        "suggested_example": result.get("suggested_example", ""),
        "example_source": result.get("example_source", ""),
        "awaiting_attachment": result.get("awaiting_attachment", False),
        "conversation": conversation_history,
        "generated_script": request.generated_script,
    }


@router.post("/{request_id}/step-attachment")
def submit_step_attachment_endpoint(
    request_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit the file/screenshot the AI asked for after several confused
    turns on the current step (see guided_engine's off-track tracking).

    Unlike /reference-file (a production extract cross-checked against
    an anomaly), this is never compared against anything — it only
    gives the AI more context for its next explanation, so the step
    stays exactly where it was.
    """
    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

    ext = os.path.splitext(file.filename or "")[1].lower()

    if ext not in ALLOWED_STEP_ATTACHMENT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Allowed: image, PDF, Word, Excel, CSV, or plain text.",
        )

    data = file.file.read()

    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")

    if len(data) > MAX_STEP_ATTACHMENT_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is too large (15MB max).")

    is_image = ext in STEP_ATTACHMENT_IMAGE_EXTENSIONS

    unique_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(STEP_ATTACHMENT_DIR, unique_name)

    with open(stored_path, "wb") as buffer:
        buffer.write(data)

    extracted_text = None

    if not is_image:
        try:
            extracted_text = extract_text(stored_path)[:20_000]
        except Exception as exc:
            logger.warning("Could not extract text from step attachment %r: %s", file.filename, exc)
            extracted_text = None

    # No OCR/vision pipeline reads an image's pixels here — the model
    # only ever sees this note, never the picture itself.
    attachment_summary = extracted_text or f"[{'Image' if is_image else 'File'} attached: {file.filename}]"

    workflow_data = json.loads(request.eval_profile) if request.eval_profile else {}
    step_index = int((workflow_data.get("step_workflow") or {}).get("current_step", 0)) if isinstance(workflow_data, dict) else 0

    attachment = StepAttachment(
        request_id=request.id,
        uploaded_by=current_user.id,
        step_index=step_index,
        original_filename=file.filename or unique_name,
        stored_path=stored_path,
        content_type=file.content_type,
        size_bytes=len(data),
        is_image=is_image,
        extracted_text=extracted_text,
    )
    db.add(attachment)
    db.commit()

    result = submit_step_attachment(request, db, attachment_summary)

    if not result.get("accepted"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("ai_response", "Could not process that attachment."))

    conversation_history = []
    if request.conversation:
        try:
            conversation_history = json.loads(request.conversation)
        except (json.JSONDecodeError, TypeError, ValueError):
            conversation_history = []

    conversation_history.append({
        "sender": "user",
        "text": f"[Attached: {file.filename}]",
        "timestamp": datetime.now().isoformat(),
    })
    conversation_history.append({
        "sender": "ai",
        "text": result.get("ai_response", ""),
        "timestamp": datetime.now().isoformat(),
    })

    request.conversation = json.dumps(conversation_history)
    db.commit()

    return {
        "request_id": request_id,
        "ai_response": result.get("ai_response", ""),
        "step_index": result.get("step_index", 0),
        "step_name": result.get("step_name", ""),
        "progress": result.get("progress", None),
        "conversation": conversation_history,
    }


@router.get("/{request_id}/completed-steps")
def get_completed_steps(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List the rules already completed for a request, with what the
    user submitted for each — the source list for editing mode.
    """
    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found."
        )

    return {"steps": list_completed_steps(request)}


@router.post("/{request_id}/step-edit")
def edit_step_answer(
    request_id: int,
    step_index: int = Form(...),
    value: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Correct the answer already submitted for a completed step,
    without disturbing the request's current position in the
    workflow.
    """
    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found."
        )

    result = edit_step(request, db, step_index, value)

    conversation_history = []
    if request.conversation:
        try:
            conversation_history = json.loads(request.conversation)
        except:
            conversation_history = []

    conversation_history.append({
        "sender": "user",
        "text": value,
        "edit": True,
        "step_index": step_index,
        "validated": bool(result.get("edited", False)),
        "timestamp": datetime.now().isoformat()
    })
    conversation_history.append({
        "sender": "ai",
        "text": result.get("ai_response", ""),
        "edit": True,
        "step_index": step_index,
        "passed": bool(result.get("edited", False)),
        "timestamp": datetime.now().isoformat()
    })

    request.conversation = json.dumps(conversation_history)
    db.commit()

    return {
        "request_id": request_id,
        "step_index": step_index,
        "edited": result.get("edited", False),
        "ai_response": result.get("ai_response", ""),
        "verdict": result.get("verdict", None),
        "conversation": conversation_history,
    }


@router.post("/{request_id}/step-regenerate")
def regenerate_step_example(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ask the AI again for the current step's example, after it
    previously failed to produce one (e.g. a Groq rate limit).
    """
    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found."
        )

    result = regenerate_current_example(request, db)

    conversation_history = []
    if request.conversation:
        try:
            conversation_history = json.loads(request.conversation)
        except:
            conversation_history = []

    conversation_history.append({
        "sender": "ai",
        "text": result.get("ai_response", ""),
        "regenerated": True,
        "timestamp": datetime.now().isoformat()
    })

    request.conversation = json.dumps(conversation_history)
    db.commit()

    return {
        "request_id": request_id,
        "ai_response": result.get("ai_response", ""),
        "regenerated": result.get("regenerated", False),
        "conversation": conversation_history,
    }


@router.post("/{request_id}/regenerate-workflow-script")
def regenerate_workflow_script(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-run script generation for a completed rules-document walkthrough.

    Covers the case where the automatic generation on the final
    step-chat turn failed (e.g. a Groq rate limit) or the user wants a
    fresh attempt — this is the manual retry for that, distinct from
    report_analyses' own /generate-script.
    """
    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")

    if request.status != "processing_completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Finish every step before generating the script.",
        )

    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == request.task_id).first()

    try:
        request.generated_script = generate_workflow_script(
            task_name=task.name if task else "",
            task_description=task.description if task else "",
            rules_content=task.rules_content if task else "",
            completed_steps=list_completed_steps(request),
            language=getattr(current_user, "language", "en") or "en",
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    db.commit()

    return {"request_id": request_id, "generated_script": request.generated_script}


def _request_progress(request) -> dict:
    """
    How far a configuration request has got.

    Prefers the step-by-step walkthrough's own count, which is the
    real measure of progress. Falls back to how many validation
    errors have been resolved, then to the request's status.
    """

    workflow = {}

    if request.eval_profile:
        try:
            profile = json.loads(request.eval_profile) or {}
            if isinstance(profile, dict):
                workflow = profile.get("step_workflow") or {}
        except (json.JSONDecodeError, TypeError, ValueError):
            workflow = {}

    if isinstance(workflow, dict) and workflow.get("total_steps"):
        total = int(workflow.get("total_steps") or 0)
        done = int(workflow.get("completed_steps") or 0)

        if total > 0:
            return {
                "completed_steps": min(done, total),
                "total_steps": total,
                "percent": round(min(done, total) / total * 100),
            }

    # No walkthrough: fall back to resolved validation errors.
    errors = []

    if request.validation_errors:
        try:
            errors = json.loads(request.validation_errors) or []
        except (json.JSONDecodeError, TypeError, ValueError):
            errors = []

    if isinstance(errors, list) and errors:
        solved = sum(1 for e in errors if isinstance(e, dict) and e.get("solved"))
        return {
            "completed_steps": solved,
            "total_steps": len(errors),
            "percent": round(solved / len(errors) * 100),
        }

    finished = request.status in (
        "script_generated",
        "processing_completed",
        "data_validated",
    )

    return {
        "completed_steps": 1 if finished else 0,
        "total_steps": 1,
        "percent": 100 if finished else 0,
    }


@router.get("/")
def list_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Every configuration request, for the dashboard.

    Returns one row per request with its task, how far it has got,
    and who is working on it — plus the totals the summary cards show.
    """

    rows = (
        db.query(ConfigurationRequest, ConfigurationTask, User)
        .outerjoin(
            ConfigurationTask,
            ConfigurationRequest.task_id == ConfigurationTask.id,
        )
        .outerjoin(User, ConfigurationRequest.user_id == User.id)
        # Newest activity first. COALESCE rather than NULLS LAST:
        # SQL Server has no NULLS LAST, and a request that has never
        # been updated should fall back to when it was created.
        .order_by(
            func.coalesce(
                ConfigurationRequest.updated_at,
                ConfigurationRequest.created_at,
            ).desc(),
            ConfigurationRequest.id.desc(),
        )
        .all()
    )

    COMPLETED = {"script_generated", "processing_completed"}
    NOT_STARTED = {"draft"}

    items = []
    completed = pending = not_started = 0
    percent_total = 0

    for request, task, owner in rows:

        progress = _request_progress(request)
        percent_total += progress["percent"]

        if request.status in COMPLETED:
            bucket = "completed"
            completed += 1
        elif request.status in NOT_STARTED:
            bucket = "not_started"
            not_started += 1
        else:
            bucket = "pending"
            pending += 1

        items.append({
            "id": request.id,
            "task_id": request.task_id,
            "task_name": task.name if task else "Unassigned task",
            "task_description": (task.description if task else None),
            "task_category": (task.category if task else None),
            "status": request.status,
            "priority": request.priority or "medium",
            "bucket": bucket,
            "progress": progress["percent"],
            "completed_steps": progress["completed_steps"],
            "total_steps": progress["total_steps"],
            "uploaded_filename": request.uploaded_filename,
            "created_at": request.created_at,
            "updated_at": request.updated_at,
            # Who is working on it.
            "owner": (
                {
                    "id": owner.id,
                    "full_name": owner.full_name,
                    "profile_picture": owner.profile_picture,
                }
                if owner
                else None
            ),
        })

    total = len(items)

    return {
        "summary": {
            "total": total,
            "completed": completed,
            "pending": pending,
            "not_started": not_started,
            # Average completion across every request.
            "overall_progress": round(percent_total / total) if total else 0,
        },
        "items": items,
    }


def _remove_uploaded_file(path: str | None) -> None:
    """
    Delete a request's uploaded file.

    Only files inside UPLOAD_DIR are touched. The stored path comes
    from the database, so it is checked against the upload directory
    before anything is removed — a path pointing elsewhere is left
    alone rather than followed.
    """

    if not path:
        return

    try:
        target = os.path.abspath(path)
        allowed_root = os.path.abspath(UPLOAD_DIR)

        if os.path.commonpath([target, allowed_root]) != allowed_root:
            logger.warning(
                "Refusing to delete a file outside the upload directory: %s",
                path,
            )
            return

        if os.path.isfile(target):
            os.remove(target)

    except (OSError, ValueError):
        # A missing or unreadable file must not block the deletion of
        # the record it belonged to.
        logger.warning(
            "Could not remove the uploaded file for a deleted request: %s",
            path,
        )


class BulkDeleteBody(BaseModel):
    ids: list[int]


PRIORITIES = ("low", "medium", "high")


class PriorityBody(BaseModel):
    priority: str


@router.patch("/{request_id}/priority", status_code=status.HTTP_200_OK)
def set_request_priority(
    request_id: int,
    body: PriorityBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Change how urgent a request is.

    The dashboard shows every user's requests to every signed-in user,
    so priority follows the same shared visibility: anyone signed in
    may change it, not just the request's original owner.
    """

    value = str(body.priority or "").strip().lower()

    if value not in PRIORITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Priority must be one of: {', '.join(PRIORITIES)}.",
        )

    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found.",
        )

    request.priority = value
    db.commit()

    return {"id": request_id, "priority": value}


# Statuses that already mean every step of the workflow is behind the
# request — reaching one of these is what unlocks the manual "mark
# complete" action below.
STEPS_FINISHED_STATUSES = {"data_validated", "script_generated", "processing_completed"}


@router.patch("/{request_id}/complete", status_code=status.HTTP_200_OK)
def complete_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark a request as fully completed.

    Only allowed once every step of its workflow is finished — either
    the status already reflects that, or the step-by-step progress
    count has reached its total.
    """

    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found.",
        )

    progress = _request_progress(request)
    all_steps_done = progress["total_steps"] > 0 and progress["completed_steps"] >= progress["total_steps"]

    if request.status not in STEPS_FINISHED_STATUSES and not all_steps_done:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Finish every step before marking this task complete.",
        )

    request.status = "processing_completed"
    db.commit()

    return {"id": request_id, "status": request.status}


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
def bulk_delete_requests(
    body: BulkDeleteBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete several configuration requests at once.

    Reports on each id rather than failing the whole batch: a
    selection containing one request the caller does not own still
    deletes the rest, and says which were refused.

    Declared before /{request_id} so "bulk-delete" is not read as an
    id.
    """

    ids = list(dict.fromkeys(body.ids or []))

    if not ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No requests were selected.",
        )

    found = (
        db.query(ConfigurationRequest)
        .filter(ConfigurationRequest.id.in_(ids))
        .all()
    )

    by_id = {request.id: request for request in found}

    deleted = []
    forbidden = []
    missing = []
    paths = []

    for request_id in ids:

        request = by_id.get(request_id)

        if request is None:
            missing.append(request_id)
            continue

        if request.user_id != current_user.id:
            forbidden.append(request_id)
            continue

        paths.append(request.uploaded_file_path)
        db.delete(request)
        deleted.append(request_id)

    if deleted:
        db.commit()

        # Only once the records are gone.
        for path in paths:
            _remove_uploaded_file(path)

    return {
        "deleted": deleted,
        "forbidden": forbidden,
        "missing": missing,
        "deleted_count": len(deleted),
    }


@router.delete("/{request_id}", status_code=status.HTTP_200_OK)
def delete_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a configuration request.

    Only the person who created it may delete it. The request's
    uploaded file, conversation and walkthrough progress go with it;
    the task template it was based on is untouched and can be used
    again.
    """

    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found.",
        )

    if request.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own requests.",
        )

    uploaded_path = request.uploaded_file_path

    db.delete(request)
    db.commit()

    # Only once the record is gone, so a failed delete cannot leave a
    # row pointing at a file that no longer exists.
    _remove_uploaded_file(uploaded_path)

    return {
        "deleted": True,
        "id": request_id,
    }


@router.get("/{request_id}")
def get_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific configuration request by ID.
    """
    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found."
        )
    
    # Parse JSON fields
    validation_errors = []
    if request.validation_errors:
        try:
            validation_errors = json.loads(request.validation_errors)
        except:
            validation_errors = []
    
    conversation = []
    if request.conversation:
        try:
            conversation = json.loads(request.conversation)
        except:
            conversation = []
    
    eval_profile = None
    if request.eval_profile:
        try:
            eval_profile = _json_safe(json.loads(request.eval_profile))
        except:
            eval_profile = None

    generated_script = request.generated_script
    analysis_state = eval_profile.get("analysis_state") if isinstance(eval_profile, dict) else None

    return {
        "id": request.id,
        "task_id": request.task_id,
        "status": request.status,
        "current_stage": request.current_stage,
        "validation_errors": validation_errors,
        "eval_profile": eval_profile,
        "conversation": conversation,
        "generated_script": generated_script,
        "anomalies": (analysis_state or {}).get("anomalies", []),
        "unresolved_issues": (analysis_state or {}).get("unresolved_issues", []),
        "correction_mode": (analysis_state or {}).get("correction_mode"),
        "needs_correction_mode_choice": report_analysis_service.needs_correction_mode_choice(analysis_state or {}),
        "uploaded_filename": request.uploaded_filename,
        "file_url": _file_url(request.uploaded_file_path),
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


@router.post("/{request_id}/resume-assistant")
def resume_assistant(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Switch a no-template request back from the specialist to the AI
    assistant, so the user can keep chatting with the assistant once
    they are done with the expert.
    """
    request = _get_request_or_404(db, request_id)

    if request.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only resume your own requests.",
        )

    if request.task_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This request already has a task template.",
        )

    request.current_stage = "with_assistant"
    request.status = "additional_information_required"

    conversation = []
    if request.conversation:
        try:
            conversation = json.loads(request.conversation)
        except (json.JSONDecodeError, TypeError, ValueError):
            conversation = []
    conversation.append({
        "sender": "ai",
        "text": "Back with the AI assistant — how can I help you continue?",
        "timestamp": datetime.now().isoformat(),
    })
    request.conversation = json.dumps(conversation)

    db.commit()

    return {
        "id": request.id,
        "status": request.status,
        "current_stage": request.current_stage,
        "conversation": conversation,
    }


@router.post("/{request_id}/chat")
def chat_with_assistant(
    request_id: int,
    message: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to the AI assistant for a specific request.
    """
    # Get the request
    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found."
        )
    
    # Get validation errors
    validation_errors = []
    if request.validation_errors:
        try:
            validation_errors = json.loads(request.validation_errors)
        except:
            validation_errors = []
    
    # Get conversation history
    conversation_history = []
    if request.conversation:
        try:
            conversation_history = json.loads(request.conversation)
        except:
            conversation_history = []
    
    # Get the task for the request
    task = db.query(ConfigurationTask).filter(
        ConfigurationTask.id == request.task_id
    ).first()
    task_name = task.name if task else "BRAINOPX Configuration"
    
    # Get per-rule verdicts from the stored eval_profile (set at upload time)
    rule_results = []
    if request.eval_profile:
        try:
            profile = json.loads(request.eval_profile)
            rule_results = profile.get("rule_results", []) or []
        except (json.JSONDecodeError, TypeError, ValueError):
            rule_results = []
    
    # If the task has rules, use the rule-aware AI response so the assistant
    # guides the user based on the task's rules and the current per-rule verdicts.
    rules = get_rules_for_task(db, request.task_id)
    try:
        if rules:
            ai_response = get_rule_aware_response(
                task_name=task_name,
                rules=rules,
                results=rule_results,
                conversation_history=conversation_history,
                user_message=message,
            )
        else:
            # Fall back to the classic validation-error AI for tasks without rules
            rules_text = ""
            parsed_rules = []
            if task:
                if task.rules_content:
                    try:
                        rules_content_obj = json.loads(task.rules_content)
                        rules_text = rules_content_obj.get("full_text", "") or ""
                    except (json.JSONDecodeError, TypeError, ValueError):
                        rules_text = task.rules_content or ""
                if task.category_metadata:
                    try:
                        category_metadata = json.loads(task.category_metadata)
                        if isinstance(category_metadata, dict):
                            parsed_rules = category_metadata.get("parsed_rules", []) or []
                    except (json.JSONDecodeError, TypeError, ValueError):
                        parsed_rules = []

            ai_response = get_ai_response(
                task_name=task_name,
                validation_errors=validation_errors,
                conversation_history=conversation_history,
                user_message=message,
                rules_content=rules_text,
                parsed_rules=parsed_rules,
            )
    except GroqNetworkError:
        ai_response = "Please check your network and retry."
    
    # Save conversation
    conversation_history.append({
        "sender": "user",
        "text": message,
        "timestamp": datetime.now().isoformat()
    })
    conversation_history.append({
        "sender": "ai",
        "text": ai_response,
        "timestamp": datetime.now().isoformat()
    })
    
    request.conversation = json.dumps(conversation_history)
    db.commit()

    return {
        "request_id": request_id,
        "user_message": message,
        "ai_response": ai_response,
        "conversation": conversation_history,
    }


# ============================================================
# REPORT ANALYSIS: reference files, conflicts, decisions, scripts
# ============================================================

def _get_request_or_404(db: Session, request_id: int) -> ConfigurationRequest:
    request = db.query(ConfigurationRequest).filter(
        ConfigurationRequest.id == request_id
    ).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    return request


@router.get("/{request_id}/anomalies")
def get_request_anomalies(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The current anomaly/conflict list for a report analysis request,
    for the chat UI to render (unknown codes still needing a reference
    file, conflicts still needing an update/ignore decision).
    """
    request = _get_request_or_404(db, request_id)
    state = report_analysis_service.get_analysis_state(request)

    return {
        "request_id": request_id,
        "current_stage": request.current_stage,
        "anomalies": state.get("anomalies", []),
        "unresolved_issues": state.get("unresolved_issues", []),
        "correction_mode": state.get("correction_mode"),
        "needs_correction_mode_choice": report_analysis_service.needs_correction_mode_choice(state),
        "all_resolved": report_analysis_service.all_resolved(request),
    }


@router.post("/{request_id}/reference-file")
def submit_reference_file(
    request_id: int,
    linked_anomaly_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a supplementary file (e.g. a production extract) to resolve
    an open unknown-code anomaly. Cross-references it against the
    primary upload and either resolves the anomaly automatically or
    turns it into a conflict that needs an update/ignore decision.
    """
    request = _get_request_or_404(db, request_id)

    try:
        result = report_analysis_service.record_reference_file(
            db,
            request,
            uploaded_by_user_id=current_user.id,
            original_filename=file.filename,
            file_bytes=file.file.read(),
            linked_anomaly_id=linked_anomaly_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    state = report_analysis_service.get_analysis_state(request)
    summary = report_analysis_service.build_anomaly_summary_message(state)

    conversation = []
    if request.conversation:
        try:
            conversation = json.loads(request.conversation)
        except (json.JSONDecodeError, TypeError, ValueError):
            conversation = []
    conversation.append({
        "sender": "ai",
        "text": summary,
        "timestamp": datetime.now().isoformat(),
    })
    request.conversation = json.dumps(conversation)
    db.commit()

    return {
        "request_id": request_id,
        "anomaly": result["anomaly"],
        "current_stage": request.current_stage,
        "ai_response": summary,
        "conversation": conversation,
        "all_resolved": report_analysis_service.all_resolved(request),
    }


class DecisionBody(BaseModel):
    anomaly_id: str
    decision: str


@router.post("/{request_id}/decision")
def submit_conflict_decision(
    request_id: int,
    body: DecisionBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Record the user's update-vs-ignore decision for a conflict anomaly.
    """
    request = _get_request_or_404(db, request_id)

    try:
        result = report_analysis_service.record_decision(
            db, request, anomaly_id=body.anomaly_id, decision=body.decision,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    ai_text = (
        f"Got it, I'll {body.decision} that record for you."
        + (" That was the last one — everything's validated now, ready to generate your script whenever you are!" if result["all_resolved"] else "")
    )

    conversation = []
    if request.conversation:
        try:
            conversation = json.loads(request.conversation)
        except (json.JSONDecodeError, TypeError, ValueError):
            conversation = []
    conversation.append({
        "sender": "ai",
        "text": ai_text,
        "timestamp": datetime.now().isoformat(),
    })
    request.conversation = json.dumps(conversation)
    db.commit()

    return {
        "request_id": request_id,
        "anomaly": result["anomaly"],
        "all_resolved": result["all_resolved"],
        "current_stage": request.current_stage,
        "ai_response": ai_text,
        "conversation": conversation,
    }


class CorrectionModeBody(BaseModel):
    mode: str  # "chat" or "excel"


@router.post("/{request_id}/correction-mode")
def submit_correction_mode(
    request_id: int,
    body: CorrectionModeBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Records whether the user wants to fix flagged anomalies by typing
    corrected values here in chat, or by reopening the Excel file and
    resubmitting it. Asked once per request, right after anomalies are
    first found (see report_analysis_service.needs_correction_mode_choice),
    so the chat doesn't just assume one path — calling this again later
    switches the choice.
    """
    request = _get_request_or_404(db, request_id)

    try:
        state = report_analysis_service.set_correction_mode(db, request, body.mode)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if body.mode == "excel":
        ai_text = (
            "Sounds good — open the file below, fix the flagged rows, and "
            "resubmit it here whenever you're ready and I'll check it again."
        )
    else:
        ai_text = "Sounds good — go ahead and send me the corrected value for each one as you fix it."

    conversation = []
    if request.conversation:
        try:
            conversation = json.loads(request.conversation)
        except (json.JSONDecodeError, TypeError, ValueError):
            conversation = []
    conversation.append({
        "sender": "ai",
        "text": ai_text,
        "timestamp": datetime.now().isoformat(),
    })
    request.conversation = json.dumps(conversation)
    db.commit()

    return {
        "request_id": request_id,
        "correction_mode": state["correction_mode"],
        "current_stage": request.current_stage,
        "ai_response": ai_text,
        "conversation": conversation,
    }


class CorrectionBody(BaseModel):
    anomaly_id: str
    corrected_value: str


@router.post("/{request_id}/correction")
def submit_correction(
    request_id: int,
    body: CorrectionBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit a corrected value for a flagged row/column. Re-validates it
    against the rule that was violated; on success, resolves the
    anomaly and flips the matching Validation Report row to solved.
    """
    request = _get_request_or_404(db, request_id)

    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == request.task_id).first()
    if not task or not task.column_rules:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This task has no column rules to validate against.")

    column_rules = json.loads(task.column_rules)

    try:
        result = report_analysis_service.resolve_with_correction(
            db, request, anomaly_id=body.anomaly_id, corrected_value=body.corrected_value,
            column_rules=column_rules,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    validation_errors = json.loads(request.validation_errors) if request.validation_errors else []

    if result["accepted"]:
        validation_service.mark_error_solved(
            validation_errors, user_message=body.corrected_value, anomaly_id=body.anomaly_id,
        )
        request.validation_errors = json.dumps(validation_errors)
        ai_text = (
            f"Nice, that fixes row {result['anomaly']['row']}, column '{result['anomaly']['column']}'."
            + (" That was the last one — everything's validated now, ready to generate your script whenever you are!" if result.get("all_resolved") else "")
        )
    else:
        ai_text = f"Hmm, that one doesn't quite work either: {result['reason']} Want to give it another try?"

    conversation = []
    if request.conversation:
        try:
            conversation = json.loads(request.conversation)
        except (json.JSONDecodeError, TypeError, ValueError):
            conversation = []
    conversation.append({
        "sender": "ai",
        "text": ai_text,
        "timestamp": datetime.now().isoformat(),
    })
    request.conversation = json.dumps(conversation)
    db.commit()

    return {
        "request_id": request_id,
        "anomaly": result["anomaly"],
        "accepted": result["accepted"],
        "all_resolved": result.get("all_resolved", False),
        "current_stage": request.current_stage,
        "validation_errors": validation_errors,
        "ai_response": ai_text,
        "conversation": conversation,
    }


@router.post("/{request_id}/generate-script")
def generate_report_script(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate the SQL script for a report analysis request, once every
    anomaly has been resolved.
    """
    request = _get_request_or_404(db, request_id)

    if not report_analysis_service.all_resolved(request):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Every anomaly must be resolved before the script can be generated.",
        )

    task = db.query(ConfigurationTask).filter(ConfigurationTask.id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    try:
        script_text, row_count = report_analysis_service.generate_sql_script(db, request, task)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    version = report_analysis_service.save_script_version(
        db, request, script_text, row_count, generated_by_user_id=current_user.id,
    )
    report_analysis_service.advance_stage(db, request, "script_generated")

    return {
        "request_id": request_id,
        "generated_script": script_text,
        "row_count": row_count,
        "version_number": version.version_number,
        "current_stage": request.current_stage,
    }


@router.get("/{request_id}/script-versions")
def list_script_versions(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """History of every SQL script generated for this request."""
    _get_request_or_404(db, request_id)

    versions = (
        db.query(ReportScriptVersion)
        .filter(ReportScriptVersion.request_id == request_id)
        .order_by(ReportScriptVersion.version_number.desc())
        .all()
    )

    return {
        "request_id": request_id,
        "versions": [
            {
                "version_number": v.version_number,
                "script_text": v.script_text,
                "row_count": v.row_count,
                "generated_at": v.generated_at,
            }
            for v in versions
        ],
    }
