"""
BRAINOPX Step-by-Step Rule Workflow Service

This service provides the workflow expected by:
    app.routers.requests

Functions exposed:
    - init_workflow()
    - get_step_initial_message()
    - process_step_input()
    - get_workflow_progress()

Workflow:

    Task Rules
        ↓
    Initialize workflow
        ↓
    Rule 1
        ↓
    Show concrete example + ask user
        ↓
    User response
        ↓
    Validate response
        ↓
    Passed?
      ├── YES → Rule 2
      └── NO  → Explain problem + remain on Rule
        ↓
    Last Rule
        ↓
    All completed
"""

import html
import json
import logging
from datetime import datetime
from typing import Any, Optional
from ..db.models import ConfigurationTask
from sqlalchemy.orm import Session

from . import composite_rules
from . import guided_engine as engine
from . import step_presenter as presenter

logger = logging.getLogger(__name__)


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _esc(value, default: str = "") -> str:
    """
    Escape a value for inclusion in a workflow message.

    These messages are rendered by the frontend via innerHTML, so
    every dynamic value must be escaped — rule text originates from
    an uploaded rules document and validation feedback originates
    from the model.
    """

    text = str(
        value
        if value is not None
        else ""
    ).strip()

    return html.escape(
        text or default
    )


# The CSS class the frontend styles each kind of line with. Every
# message goes through here, so a later step is presented exactly
# like the first — previously only the opening message was styled
# and everything after it arrived as undifferentiated text.
_ROLE_CLASS = {
    presenter.ROLE_HEADING: "workflow-step",
    presenter.ROLE_INSTRUCTION: "rule-description",
    presenter.ROLE_EXAMPLE: "example-box",
    presenter.ROLE_PROBLEM: "failure-message",
    presenter.ROLE_CONFIRMATION: "success-message",
    presenter.ROLE_TEXT: "rule-description",
}


def _render_blocks(blocks) -> str:
    """
    Render tagged message lines as the markup the frontend styles.

    Newlines inside a line become <br>, since this is placed with
    innerHTML where a newline collapses — a table example is several
    lines and has to keep them.
    """

    parts = []

    for item in blocks or []:

        if isinstance(item, dict):
            role = item.get("role", presenter.ROLE_TEXT)
            text = item.get("text", "")
        else:
            role = presenter.ROLE_TEXT
            text = item

        if not str(text).strip():
            continue

        # A table block is already markup, with every cell escaped
        # when it was placed. Escaping it again would print the tags.
        if role == presenter.ROLE_TABLE:
            parts.append(str(text))
            continue

        css_class = _ROLE_CLASS.get(role, "rule-description")

        parts.append(
            f'<span class="{css_class}">'
            f'{_esc(text).replace(chr(10), "<br>")}'
            f'</span>'
        )

    return "".join(parts)



def _safe_json_loads(value: Any, default: Any = None) -> Any:
    """
    Safely parse JSON.
    """
    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def _safe_json_dumps(value: Any) -> str:
    """
    Safely serialize JSON.
    """
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
        )
    except (TypeError, ValueError):
        return "{}"


def _get_rule_name(rule: dict, index: int) -> str:
    """
    Get a readable rule name.
    """
    return str(
        rule.get(
            "name",
            f"Rule {index + 1}",
        )
    ).strip() or f"Rule {index + 1}"


def _get_rule_description(rule: dict) -> str:
    """
    Get the most useful description available.
    """
    description = (
        rule.get("description")
        or rule.get("task")
        or rule.get("expected_outcome")
        or ""
    )

    return str(description).strip()


# ============================================================
# WORKFLOW STORAGE
# ============================================================

def _get_workflow_data(request) -> dict:
    """
    Workflow state is stored inside request.eval_profile.

    Existing eval_profile data such as rule_results is preserved.
    """

    profile = _safe_json_loads(
        getattr(request, "eval_profile", None),
        {},
    )

    if not isinstance(profile, dict):
        profile = {}

    workflow = profile.get("step_workflow")

    if not isinstance(workflow, dict):
        workflow = {}

    return workflow


def _save_workflow_data(
    request,
    workflow: dict,
) -> None:
    """
    Save workflow state while preserving other eval_profile data.
    """

    profile = _safe_json_loads(
        getattr(request, "eval_profile", None),
        {},
    )

    if not isinstance(profile, dict):
        profile = {}

    profile["step_workflow"] = workflow

    request.eval_profile = _safe_json_dumps(profile)


# ============================================================
# INITIALIZE WORKFLOW
# ============================================================

def init_workflow(
    request,
    db: Session,
    rules: list[dict],
) -> dict:
    """
    Initialize the step-by-step workflow for a configuration request.

    Parameters:
        request:
            ConfigurationRequest SQLAlchemy object.

        db:
            SQLAlchemy session.

        rules:
            List of task rules.

    Returns:
        Workflow state dictionary.
    """

    if rules is None:
        rules = []

    # Make sure rules are dictionaries.
    normalized_rules = []

    for index, rule in enumerate(rules):

        if not isinstance(rule, dict):
            continue

        normalized_rule = dict(rule)

        normalized_rule["id"] = rule.get(
            "id",
            index + 1,
        )

        normalized_rule["name"] = _get_rule_name(
            rule,
            index,
        )

        normalized_rule["description"] = (
            _get_rule_description(rule)
        )

        normalized_rule["task"] = str(
            rule.get(
                "task",
                rule.get(
                    "description",
                    "",
                ),
            )
        ).strip()

        normalized_rule["expected_outcome"] = str(
            rule.get(
                "expected_outcome",
                "",
            )
        ).strip()

        if not isinstance(
            normalized_rule.get("keywords"),
            list,
        ):
            normalized_rule["keywords"] = []

        # Preserve any precomputed example values so they are available
        # for step-by-step guidance and validation.
        for extra_key in ("example_input", "suggested_fix"):
            if extra_key in rule and rule[extra_key]:
                normalized_rule[extra_key] = rule[extra_key]

        normalized_rules.append(
            normalized_rule
        )

    workflow = {
        "initialized": True,
        "current_step": 0,
        "total_steps": len(normalized_rules),
        "completed_steps": 0,
        "all_completed": len(normalized_rules) == 0,
        "rules": normalized_rules,
        "results": [],
        "started_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    _save_workflow_data(
        request,
        workflow,
    )

    # Persist immediately.
    try:
        db.add(request)
        db.commit()
        db.refresh(request)
    except Exception:
        db.rollback()
        raise

    return workflow


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

def init_step_workflow(
    request,
    db: Session,
    rules: list[dict],
) -> dict:
    """
    Compatibility wrapper.

    Some parts of BRAINOPX may call init_step_workflow()
    while others call init_workflow().
    """

    return init_workflow(
        request=request,
        db=db,
        rules=rules,
    )


# ============================================================
# CURRENT RULE
# ============================================================

def _get_current_rule(
    workflow: dict,
) -> Optional[dict]:

    rules = workflow.get("rules") or []

    current_step = int(
        workflow.get(
            "current_step",
            0,
        )
    )

    if current_step < 0:
        current_step = 0

    if current_step >= len(rules):
        return None

    rule = rules[current_step]

    if not isinstance(rule, dict):
        return None

    return rule


# ============================================================
# INITIAL STEP MESSAGE
# ============================================================

def get_step_initial_message(
    request,
    db: Session,
) -> str:
    """
    Generate the initial message for the current workflow step.

    IMPORTANT:
    The example is generated from the current rule's
    deterministic constraints. A stored example is only
    used if it has already been deterministically validated.
    """

    workflow = _get_workflow_data(request)

    if not workflow:
        return "The step-by-step workflow has not been initialized."

    if workflow.get("all_completed"):
        return "All rules have been completed successfully."

    current_step = int(
        workflow.get("current_step", 0)
    )

    total_steps = int(
        workflow.get("total_steps", 0)
    )

    rule = _get_current_rule(workflow)

    if not rule:
        return "The workflow has no remaining rules."

    # ========================================================
    # GET TASK NAME
    # ========================================================

    task_name = "TASK"

    try:
        task = (
            db.query(ConfigurationTask)
            .filter(
                ConfigurationTask.id == request.task_id
            )
            .first()
        )

        if task and task.name:
            task_name = str(
                task.name
            ).strip().upper()

    except Exception as exc:
        logger.warning(
            "Could not retrieve task name: %s",
            exc,
        )

    # ========================================================
    # USE (OR BUILD) THE REAL ENGINE STEP FOR THIS RULE
    #
    # Every later turn works from workflow["steps"], not the raw
    # rule list. Building it here — rather than a throwaway dict, as
    # this used to — means a composite first rule has somewhere to
    # hold its collection state before the user's first reply, and
    # the opening message goes through the exact same
    # example-preparation and prompt-building code every later step
    # uses, so the two can never drift apart in wording or styling.
    # ========================================================

    rules = workflow.get("rules") or []
    steps = workflow.get("steps")

    if not isinstance(steps, list) or len(steps) != len(rules):
        steps = engine.build_steps(rules)

    step = steps[current_step]

    engine.prepare_example(step, rule, force_new=True)
    engine.ensure_collection_started(step)

    workflow["steps"] = steps
    workflow["updated_at"] = (
        datetime.now().isoformat()
    )

    _save_workflow_data(
        request,
        workflow,
    )

    try:
        db.add(request)
        db.commit()
        db.refresh(request)

    except Exception as exc:
        logger.warning(
            "Could not persist workflow message: %s",
            exc,
        )
        db.rollback()

    # ========================================================
    # BUILD RESPONSE
    # ========================================================

    prompt_blocks = presenter.build_step_prompt(
        step,
        current_step,
        total_steps,
    )

    return (
        f'<span class="task-title">'
        f'Welcome to the task creation '
        f'<strong>{_esc(task_name)}</strong>'
        f'</span>'
        + _render_blocks(prompt_blocks)
    )


# ============================================================
# WORKFLOW PROGRESS
# ============================================================

def get_workflow_progress(
    request,
) -> Optional[dict]:
    """
    Return the current workflow progress.
    """

    workflow = _get_workflow_data(request)

    if not workflow:
        return None

    total_steps = int(
        workflow.get(
            "total_steps",
            0,
        )
    )

    current_step = int(
        workflow.get(
            "current_step",
            0,
        )
    )

    completed_steps = int(
        workflow.get(
            "completed_steps",
            0,
        )
    )

    if total_steps > 0:

        percentage = round(
            (
                completed_steps
                / total_steps
            )
            * 100,
            2,
        )

    else:
        percentage = 100.0

    current_rule = _get_current_rule(
        workflow
    )

    current_rule_name = None

    if current_rule:

        current_rule_name = _get_rule_name(
            current_rule,
            current_step,
        )

    # Prefer the per-step value guided_engine tracks (set once the
    # walkthrough's steps exist); fall back to the value recorded
    # against the rule itself for the very first message, before any
    # step has been built yet.
    steps = workflow.get("steps")
    current_engine_step = (
        steps[current_step]
        if isinstance(steps, list) and current_step < len(steps)
        else None
    )

    example_source = ""

    if current_engine_step:
        example_source = current_engine_step.get("example_source", "")
    elif current_rule:
        example_source = current_rule.get("example_source", "")

    return {
        "total_steps": total_steps,
        "current_step": current_step,
        "current_step_number": (
            current_step + 1
            if current_rule
            else total_steps
        ),
        "completed_steps": completed_steps,
        "remaining_steps": max(
            total_steps - completed_steps,
            0,
        ),
        "percentage": percentage,
        "all_completed": bool(
            workflow.get(
                "all_completed",
                False,
            )
        ),
        "current_rule": current_rule_name,
        "current_rule_id": (
            current_rule.get("id")
            if current_rule
            else None
        ),
        "example_source": example_source,
        "awaiting_attachment": bool(
            current_engine_step and current_engine_step.get("awaiting_attachment")
        ),
        "steps": (
            [presenter.public_step(s) for s in steps]
            if isinstance(steps, list)
            else []
        ),
    }


# ============================================================
# PROCESS STEP INPUT
# ============================================================

def process_step_input(
    request,
    db: Session,
    user_message: str,
) -> dict:
    """
    Judge one submitted value and advance if it is correct.

    The decision — validate, stay or advance, and what the user is
    told — comes from guided_engine, the same machine the skill-engine
    walkthrough runs on. This function only loads and saves workflow
    state on the configuration request.
    """

    user_message = str(
        user_message or ""
    ).strip()

    workflow = _get_workflow_data(request)

    if not workflow:
        return {
            "ai_response": (
                "The step-by-step workflow "
                "has not been initialized."
            ),
            "step_index": 0,
            "step_name": "",
            "status": "not_initialized",
            "passed": False,
            "all_completed": False,
            "progress": None,
        }

    rules = workflow.get("rules", []) or []

    current_step = int(
        workflow.get("current_step", 0)
    )

    if current_step >= len(rules):
        return {
            "ai_response": "All rules have been completed.",
            "step_index": current_step,
            "step_name": "",
            "status": "completed",
            "passed": True,
            "all_completed": True,
            "progress": get_workflow_progress(request),
        }

    # ================================================
    # STEP STATE
    #
    # Older workflows stored only rules. Build the steps once and
    # keep them from then on, so example and attempt state persists.
    # ================================================

    steps = workflow.get("steps")

    if not isinstance(steps, list) or len(steps) != len(rules):
        steps = engine.build_steps(rules)

        # Carry over the example each rule already owns, and arm
        # collection on whichever step is current — get_step_initial_
        # message() normally does this first, but a workflow reaching
        # here without ever having shown that message (an older
        # workflow row, or a caller that skipped it) must not land a
        # composite first step in the whole-blob path by accident.
        for step, rule in zip(steps, rules):
            engine.prepare_example(step, rule, force_new=True)

        if 0 <= current_step < len(steps):
            engine.ensure_collection_started(steps[current_step])

    # ================================================
    # ONE TURN
    # ================================================

    turn = engine.take_turn(
        steps=steps,
        current_index=current_step,
        rules=rules,
        user_input=user_message,
    )

    verdict = turn["verdict"]

    engine.record_exchange(
        turn["step"],
        user_message,
        " ".join(turn["message_lines"][:2]),
    )

    ai_response = _render_blocks(turn["message_blocks"])

    # ================================================
    # PERSIST
    # ================================================

    if turn["passed"]:
        rule = rules[current_step]
        rule["completed"] = True
        rule["user_value"] = user_message
        rules[current_step] = rule

    workflow["rules"] = rules
    workflow["steps"] = steps
    workflow["current_step"] = turn["current_index"]
    workflow["completed_steps"] = sum(
        1
        for step in steps
        if step.get("status") == "completed"
    )
    workflow["all_completed"] = turn["all_completed"]
    workflow["updated_at"] = datetime.now().isoformat()

    if turn["all_completed"]:
        workflow["completed_at"] = datetime.now().isoformat()

    _save_workflow_data(
        request,
        workflow,
    )

    try:
        db.add(request)
        db.commit()
        db.refresh(request)

    except Exception as exc:
        logger.exception(
            "Failed to save workflow state: %s",
            exc,
        )
        db.rollback()

    focus_step = turn["next_step"] or turn["step"]

    return {
        "ai_response": ai_response,

        # The step this response is about...
        "step_index": current_step,

        "step_name": presenter.step_label(turn["step"]),

        # ...and where the user stands after it.
        "current_step_index": turn["current_index"],
        "status": (
            "completed"
            if turn["all_completed"]
            else ("next_step" if turn["passed"] else "needs_work")
        ),
        "passed": turn["passed"],
        "validated": True,
        "verdict": turn["public_verdict"],
        "suggested_example": str(
            focus_step.get("suggested_example") or ""
        ),
        "example_source": str(
            focus_step.get("example_source") or ""
        ),
        "all_completed": turn["all_completed"],
        "awaiting_attachment": bool(focus_step.get("awaiting_attachment")),
        "progress": get_workflow_progress(request),
    }


# ============================================================
# RESOLVING AN ATTACHMENT THE AI ASKED FOR
# ============================================================

def submit_step_attachment(
    request,
    db: Session,
    attachment_summary: str,
) -> dict:
    """
    Feed a just-uploaded file/screenshot to the step the AI asked for
    it on, and reply with an explanation informed by it.

    Mirrors process_step_input's own workflow/steps loading, since
    guided_engine.resolve_attachment needs the same live step objects
    take_turn() works from. The step this applies to is whichever one
    is current — the router only accepts an upload while that step's
    awaiting_attachment flag is set, so there is no ambiguity about
    which step it belongs to.
    """

    workflow = _get_workflow_data(request)

    if not workflow:
        return {
            "ai_response": "The step-by-step workflow has not been initialized.",
            "step_index": 0,
            "accepted": False,
        }

    rules = workflow.get("rules", []) or []
    current_step = int(workflow.get("current_step", 0))

    if current_step >= len(rules):
        return {
            "ai_response": "All rules have been completed.",
            "step_index": current_step,
            "accepted": False,
        }

    steps = workflow.get("steps")

    if not isinstance(steps, list) or len(steps) != len(rules):
        steps = engine.build_steps(rules)

        for step, rule in zip(steps, rules):
            engine.prepare_example(step, rule, force_new=True)

    step = steps[current_step]

    if not step.get("awaiting_attachment"):
        return {
            "ai_response": "This step isn't waiting on an attachment right now.",
            "step_index": current_step,
            "accepted": False,
        }

    turn = engine.resolve_attachment(
        steps=steps,
        current_index=current_step,
        rules=rules,
        step=step,
        attachment_summary=attachment_summary,
    )

    engine.record_exchange(
        turn["step"],
        "[attachment]",
        " ".join(turn["message_lines"][:2]),
    )

    ai_response = _render_blocks(turn["message_blocks"])

    workflow["steps"] = steps
    workflow["updated_at"] = datetime.now().isoformat()

    _save_workflow_data(request, workflow)

    try:
        db.add(request)
        db.commit()
        db.refresh(request)
    except Exception as exc:
        logger.exception("Failed to save state after a step attachment: %s", exc)
        db.rollback()

    return {
        "ai_response": ai_response,
        "step_index": current_step,
        "step_name": presenter.step_label(turn["step"]),
        "accepted": True,
        "progress": get_workflow_progress(request),
    }


# ============================================================
# EDITING AN ALREADY-COMPLETED STEP
# ============================================================

def list_completed_steps(request) -> list[dict]:
    """
    Completed rules of this request's workflow, with what the user
    submitted for each — the "editing mode" source list.
    """

    workflow = _get_workflow_data(request)

    steps = workflow.get("steps") or []

    return [
        composite_rules.completed_step_preview(step)
        for step in steps
        if step.get("status") == "completed"
    ]


def edit_step(
    request,
    db: Session,
    step_index: int,
    value: str,
) -> dict:
    """
    Correct the answer already submitted for a completed step.

    Unlike process_step_input, this never touches current_step,
    completed_steps or all_completed — the user resumes exactly where
    they were once the correction is judged.
    """

    value = str(value or "").strip()

    workflow = _get_workflow_data(request)

    if not workflow:
        return {
            "edited": False,
            "step_index": step_index,
            "ai_response": (
                "The step-by-step workflow has not been initialized."
            ),
        }

    rules = workflow.get("rules", []) or []
    steps = workflow.get("steps")

    if not isinstance(steps, list) or len(steps) != len(rules):
        steps = engine.build_steps(rules)

        for step, rule in zip(steps, rules):
            engine.prepare_example(step, rule, force_new=True)

    if (
        not (0 <= step_index < len(steps))
        or steps[step_index].get("status") != "completed"
    ):
        return {
            "edited": False,
            "step_index": step_index,
            "ai_response": "That step cannot be edited right now.",
        }

    result = engine.edit_completed_step(
        steps=steps,
        edit_index=step_index,
        rules=rules,
        user_input=value,
    )

    if result["edited"] and 0 <= step_index < len(rules):
        rules[step_index]["user_value"] = value

    workflow["steps"] = steps
    workflow["rules"] = rules
    workflow["updated_at"] = datetime.now().isoformat()

    _save_workflow_data(
        request,
        workflow,
    )

    try:
        db.add(request)
        db.commit()
        db.refresh(request)

    except Exception as exc:
        logger.exception(
            "Failed to save an edited step: %s",
            exc,
        )
        db.rollback()

    return {
        "edited": result["edited"],
        "step_index": step_index,
        "ai_response": _render_blocks(result["message_blocks"]),
        "verdict": result["public_verdict"],
    }


# ============================================================
# REGENERATING THE CURRENT STEP'S EXAMPLE
# ============================================================

def regenerate_current_example(
    request,
    db: Session,
) -> dict:
    """
    Ask the AI again for the current step's example, after it
    previously failed to produce one (e.g. a Groq rate limit).

    Always targets the workflow's current step, the same one every
    other endpoint in this module acts on.
    """

    workflow = _get_workflow_data(request)

    if not workflow or workflow.get("all_completed"):
        return {
            "regenerated": False,
            "ai_response": "There is nothing to regenerate right now.",
        }

    rules = workflow.get("rules", []) or []
    steps = workflow.get("steps")

    if not isinstance(steps, list) or len(steps) != len(rules):
        steps = engine.build_steps(rules)

        for step, rule in zip(steps, rules):
            engine.prepare_example(step, rule, force_new=True)

    current_step = int(
        workflow.get("current_step", 0)
    )

    if not (0 <= current_step < len(steps)):
        return {
            "regenerated": False,
            "ai_response": "There is nothing to regenerate right now.",
        }

    step = steps[current_step]
    rule = rules[current_step] if current_step < len(rules) else None

    engine.prepare_example(step, rule, force_new=True)

    workflow["steps"] = steps
    workflow["updated_at"] = datetime.now().isoformat()

    _save_workflow_data(
        request,
        workflow,
    )

    try:
        db.add(request)
        db.commit()
        db.refresh(request)

    except Exception as exc:
        logger.exception(
            "Failed to save a regenerated example: %s",
            exc,
        )
        db.rollback()

    total_steps = int(
        workflow.get("total_steps", 0)
    )

    prompt_blocks = presenter.build_step_prompt(
        step,
        current_step,
        total_steps,
    )

    return {
        "regenerated": step.get("example_source") == "ai",
        "ai_response": _render_blocks(prompt_blocks),
    }


# ============================================================
# OPTIONAL ALIAS
# ============================================================

def process_step(
    request,
    db: Session,
    user_message: str,
) -> dict:
    """
    Compatibility alias for code that may call process_step().
    """

    return process_step_input(
        request=request,
        db=db,
        user_message=user_message,
    )