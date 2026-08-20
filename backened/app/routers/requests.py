import os
import json
import logging
import uuid
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime

from ..db.database import get_db
from ..db.models import ConfigurationTask, ConfigurationRequest, User
from ..db.deps import get_current_user
from ..services.excel_service import extract_column_headers
from ..services.validation_service import validate_data_rows
from ..services.template_matcher import auto_match_template, get_all_templates, get_match_summary
from ..services.groq_service import get_ai_response, get_rule_aware_response, run_rule_workflow, parse_rules_to_json
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
)

router = APIRouter(prefix="/api/requests", tags=["requests"])

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join("uploads", "requests")
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
    
    # If no match found, return templates for manual selection
    if not matched_task:
        return {
            "error": "No matching template found",
            "match_score": match_score,
            "available_templates": all_templates,
            "uploaded_file": file.filename,
            "uploaded_file_path": saved_path,
            "requires_manual_selection": True
        }
    
    # Extract data rows from the file
    df = pd.read_excel(saved_path, dtype=str)
    data_rows = []
    for idx, row in df.iterrows():
        row_data = row.to_dict()
        row_data["_row_number"] = idx + 2  # Excel row number (1-indexed, skipping header)
        data_rows.append(row_data)
    
    # Run validation using the matched task
    validation_errors = []
    if matched_task.column_rules:
        column_rules = json.loads(matched_task.column_rules) if matched_task.column_rules else []
        validation_errors = validate_data_rows(db, data_rows, column_rules)
    
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
        except Exception as e:
            # If rule evaluation fails, don't block the upload
            rule_results = []
            ai_welcome_message = (
                f"Your file has been received for task **'{matched_task.name}'**. "
                "I wasn't able to analyse it against the rules automatically. "
                "Please tell me what you'd like to achieve and I'll guide you."
            )

    # Initial conversation: seed with the AI's instant rule-aware response
    conversation = []
    if ai_welcome_message:
        conversation.append({
            "sender": "ai",
            "text": ai_welcome_message,
            "timestamp": datetime.now().isoformat(),
        })

# Create the configuration request
    new_request = ConfigurationRequest(
        task_id=matched_task.id,
        user_id=current_user.id,
        status="file_submitted",
        uploaded_filename=file.filename,
        uploaded_file_path=saved_path,
        validation_errors=json.dumps(validation_errors),
        eval_profile=json.dumps({"rule_results": rule_results}) if rule_results else None,
        conversation=json.dumps(conversation),
    )
    
    db.add(new_request)
    db.commit()
    db.refresh(new_request)

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
    
    # Get match summary
    uploaded_columns = extract_column_headers(saved_path)
    expected_columns = json.loads(matched_task.expected_columns) if matched_task.expected_columns else []
    match_summary = get_match_summary(uploaded_columns, expected_columns)
    
    return {
        "id": new_request.id,
        "task_id": matched_task.id,
        "task_name": matched_task.name,
        "status": new_request.status,
        "validation_errors": validation_errors,
        "rule_results": rule_results,
        "ai_welcome_message": ai_welcome_message,
        "conversation": conversation,
        "step_progress": step_progress,
        "match_score": match_score,
        "match_summary": match_summary,
        "uploaded_file": file.filename,
    }


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
        row_data = row.to_dict()
        row_data["_row_number"] = idx + 2
        data_rows.append(row_data)
    
    # Run validation
    validation_errors = []
    if task.column_rules:
        column_rules = json.loads(task.column_rules) if task.column_rules else []
        validation_errors = validate_data_rows(db, data_rows, column_rules)
    
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
        except Exception:
            rule_results = []
            ai_welcome_message = (
                f"Your file has been received for task **'{task.name}'**. "
                "I wasn't able to analyse it against the rules automatically. "
                "Please tell me what you'd like to achieve and I'll guide you."
            )

    conversation = []
    if ai_welcome_message:
        conversation.append({
            "sender": "ai",
            "text": ai_welcome_message,
            "timestamp": datetime.now().isoformat(),
        })

    # Create the configuration request
    new_request = ConfigurationRequest(
        task_id=task.id,
        user_id=current_user.id,
        status="file_submitted",
        uploaded_filename=file.filename,
        uploaded_file_path=saved_path,
        validation_errors=json.dumps(validation_errors),
        eval_profile=json.dumps({"rule_results": rule_results}) if rule_results else None,
        conversation=json.dumps(conversation),
    )
    
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    return {
        "id": new_request.id,
        "task_id": task.id,
        "task_name": task.name,
        "status": new_request.status,
        "validation_errors": validation_errors,
        "rule_results": rule_results,
        "ai_welcome_message": ai_welcome_message,
        "conversation": conversation,
        "uploaded_file": file.filename,
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
    
    # Update request status based on workflow completion
    if result.get("all_completed", False):
        request.status = "data_validated"
        db.commit()
    
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

    Only the person who owns it may change it, matching who is
    allowed to delete it.
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

    if request.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only change your own requests.",
        )

    request.priority = value
    db.commit()

    return {"id": request_id, "priority": value}


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
            eval_profile = json.loads(request.eval_profile)
        except:
            eval_profile = None
    
    generated_script = request.generated_script
    
    return {
        "id": request.id,
        "task_id": request.task_id,
        "status": request.status,
        "validation_errors": validation_errors,
        "eval_profile": eval_profile,
        "conversation": conversation,
        "generated_script": generated_script,
        "uploaded_filename": request.uploaded_filename,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


@router.post("/{request_id}/chat")
def chat_with_assistant(
    request_id: int,
    message: str = Form(...),
    attachment: UploadFile = File(None),
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
