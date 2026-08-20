"""
skill_engine.py — Rule Engine Router

Each rule triggers its own AI workflow to help the user achieve that rule's task.
"""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import User, ConfigurationTask
from ..db.deps import get_current_user
from ..services.skill_engine_service import (
    parse_task_rules,
    start_run,
    get_run,
    add_rule_followup,
    re_evaluate_rule,
)
from ..services.rule_router_service import (
    route_user_message,
    init_guided_session,
    process_guided_input,
    get_guided_session,
    list_completed_steps,
    edit_guided_step,
)

router = APIRouter(prefix="/api/skill-engine", tags=["skill_engine"])

UPLOAD_DIR = os.path.join("uploads", "skill_engine")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/tasks/{task_id}/parse-rules")
def api_parse_task_rules(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Parses the rules file of a Skill Engine task into structured rules.
    The parsed rules are cached on the task's category_metadata.
    """
    task = db.query(ConfigurationTask).filter(
        ConfigurationTask.id == task_id,
        ConfigurationTask.is_active == True,  # noqa: E712
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task.category != "skill_engine":
        raise HTTPException(
            status_code=400,
            detail="Selected task is not a Skill Engine task.",
        )

    rules = parse_task_rules(db, task_id)
    return {
        "task_id": task_id,
        "task_name": task.name,
        "rules_count": len(rules),
        "rules": rules,
    }


@router.post("/runs")
def api_start_run(
    task_id: int = Form(None),
    file: UploadFile = File(None),
    input_file: UploadFile = File(None),
    input_text: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Starts a Rule Engine run.

    Rules source (choose one):
        - task_id: use an existing Skill Engine task's rules file.
        - file: upload a standalone rules file (.txt, .pdf, .docx, .xlsx, etc.)

    Input source (choose one):
        - input_file: upload a file with the data/text to evaluate.
        - input_text: paste the data/text to evaluate directly.

    Returns a run_id with per-rule AI workflow results.
    """
    rules_file_path = None
    input_file_path = None

    # Save uploaded rules file if provided
    if file:
        ext = os.path.splitext(file.filename)[1].lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        rules_file_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(rules_file_path, "wb") as buffer:
            buffer.write(file.file.read())

    # Save uploaded input file if provided
    if input_file:
        ext = os.path.splitext(input_file.filename)[1].lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        input_file_path = os.path.join(UPLOAD_DIR, unique_name)
        with open(input_file_path, "wb") as buffer:
            buffer.write(input_file.file.read())

    return start_run(
        db,
        user_id=current_user.id,
        task_id=task_id,
        rules_file_path=rules_file_path,
        input_file_path=input_file_path,
        input_text=input_text,
    )


@router.get("/runs/{run_id}")
def api_get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a Rule Engine run with its per-rule results."""
    return get_run(db, run_id)


@router.post("/runs/{run_id}/rules/{rule_id}/chat")
def api_rule_followup(
    run_id: int,
    rule_id: int,
    message: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a follow-up message for a specific rule's conversation thread.
    The AI responds in the context of that single rule.
    """
    return add_rule_followup(
        db,
        run_id=run_id,
        rule_id=rule_id,
        user_message=message,
    )


@router.post("/runs/{run_id}/rules/{rule_id}/re-evaluate")
def api_re_evaluate_rule(
    run_id: int,
    rule_id: int,
    input_text: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Re-runs the AI workflow for a single rule with updated input.
    This is useful when the user has made changes and wants a fresh verdict.
    """
    return re_evaluate_rule(
        db,
        run_id=run_id,
        rule_id=rule_id,
        user_input=input_text,
    )


@router.post("/runs/{run_id}/route")
def api_route_message(
    run_id: int,
    message: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Route a user's free-form message to the most relevant rule in the run.
    The AI analyses the message against each rule's task and keywords,
    returns which rule it matches best, and provides a rule-specific response.
    """
    return route_user_message(
        db,
        run_id=run_id,
        user_message=message,
    )


@router.post("/guided-sessions")
def api_start_guided_session(
    run_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start a guided step-by-step walkthrough for a run.
    The AI walks the user through each rule's task one at a time.
    Returns the first step's prompt and the session_id.
    """
    return init_guided_session(
        db,
        run_id=run_id,
        user_id=current_user.id,
    )


@router.post("/guided-sessions/{session_id}/message")
def api_guided_message(
    session_id: str,
    message: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to an active guided session.
    The AI processes the input against the current step (rule).
    Advances to the next step when the current one is passed.
    """
    return process_guided_input(
        db,
        session_id=session_id,
        user_input=message,
        user_id=current_user.id,
    )


@router.get("/guided-sessions/{session_id}")
def api_get_guided_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current state of a guided session.
    """
    return get_guided_session(
        db,
        session_id=session_id,
        user_id=current_user.id,
    )


@router.get("/guided-sessions/{session_id}/completed-steps")
def api_list_completed_guided_steps(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List the steps already completed in a guided session, with what
    the user submitted for each — the source list for editing mode.
    """
    return list_completed_steps(
        db,
        session_id=session_id,
        user_id=current_user.id,
    )


@router.post("/guided-sessions/{session_id}/edit")
def api_edit_guided_step(
    session_id: str,
    step_index: int = Form(...),
    value: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Correct the answer already submitted for a completed step of a
    guided session, without disturbing the session's current position
    in the walkthrough.
    """
    return edit_guided_step(
        db,
        session_id=session_id,
        step_index=step_index,
        user_input=value,
        user_id=current_user.id,
    )
