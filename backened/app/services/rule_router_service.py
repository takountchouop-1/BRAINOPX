"""
rule_router_service.py

Rule Router orchestration layer.

Responsibilities:

1. Route free-form user messages to a rule.
2. Run guided rule walkthroughs.
3. Generate a separate example for EVERY rule.
4. Validate generated examples against the correct rule.
5. Persist generated examples inside the current guided session.
6. Never reuse the previous rule's example for the next rule.

Guided sessions are stored in the guided_sessions table, keyed by their
own indexed session_id. Step progress is written to that row only, so a
submission never rewrites — and never clobbers — the run's results blob.
"""

import html
import json
import logging
import uuid
from datetime import datetime

from fastapi import HTTPException

from app.services.groq_service import (
    route_message_to_rule,
    run_rule_followup,
)

from app.services import composite_rules
from app.services import guided_engine as engine
from app.services import step_presenter as presenter


logger = logging.getLogger(__name__)

_STEP_BG_COLOR = "#4f46e5"


def _esc(value, default: str = "") -> str:
    """
    Escape a value for inclusion in an ai_response.

    ai_response is rendered by the frontend via innerHTML, so every
    dynamic value interpolated into it must be escaped — including
    model-generated text (verdict summary / guidance / questions) and
    rule text, which originates from an uploaded rules document.
    """

    text = str(
        value
        if value is not None
        else ""
    ).strip()

    return html.escape(
        text or default
    )


def _html_message(blocks) -> str:
    """
    Join message lines into the HTML the frontend renders.

    Line breaks become <br> rather than newlines: the client uses
    innerHTML, where a newline collapses to a space. A list example is
    several lines and has to keep its shape.

    A table block is already markup — composite_rules escaped every
    cell as it placed it — so it passes through untouched. Escaping it
    again would print the tags.
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

        if role == presenter.ROLE_TABLE:
            parts.append(str(text))
            continue

        parts.append(_esc(text).replace("\n", "<br>"))

    return "<br><br>".join(parts)


# ============================================================================
# JSON / DATABASE HELPERS
# ============================================================================

def _load_json(raw, default):
    """Safely decode JSON."""

    if not raw:
        return default

    try:
        return json.loads(raw)
    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        return default


def _load_run_metadata(run) -> dict:
    """
    Load extended run metadata.

    Supports both:

    Legacy:
        [...]

    New:
        {
            "results": [...],
            "guided_sessions": {...}
        }
    """

    if not getattr(run, "results_json", None):
        return {
            "results": [],
            "guided_sessions": {},
        }

    data = _load_json(
        run.results_json,
        None,
    )

    if isinstance(data, list):
        return {
            "results": data,
            "guided_sessions": {},
        }

    if isinstance(data, dict):
        data.setdefault("results", [])
        data.setdefault("guided_sessions", {})
        return data

    return {
        "results": [],
        "guided_sessions": {},
    }


def get_run_results_list(run) -> list:
    """Return per-rule results."""

    metadata = _load_run_metadata(run)

    return metadata.get(
        "results",
        [],
    )


# ============================================================================
# GUIDED SESSION PERSISTENCE
# ============================================================================

def _session_to_dict(record) -> dict:
    """Inflate a GuidedSession row into the working session dict."""

    return {
        "session_id": record.session_id,

        "run_id": record.run_id,

        "steps": _load_json(
            record.steps_json,
            [],
        ),

        "current_step_index": int(
            record.current_step_index or 0
        ),

        "total_steps": int(
            record.total_steps or 0
        ),

        "all_completed": bool(
            record.all_completed
        ),

        "started_at": (
            record.started_at.isoformat()
            if record.started_at
            else None
        ),

        "completed_at": (
            record.completed_at.isoformat()
            if record.completed_at
            else None
        ),
    }


def _load_session_record(
    db,
    *,
    session_id: str,
    user_id: int | None = None,
):
    """
    Fetch a guided session by its own id.

    A direct indexed lookup — no scan over the user's recent runs, so a
    session stays reachable however old the run behind it is.
    """

    from app.db.models import GuidedSession

    query = db.query(GuidedSession).filter(
        GuidedSession.session_id == session_id
    )

    record = query.first()

    if not record:

        raise HTTPException(
            status_code=404,
            detail="Guided session not found.",
        )

    # Ownership is checked against the session's own user_id rather than
    # inferred from which runs happen to belong to the caller.

    if (
        user_id is not None
        and record.user_id != user_id
    ):

        raise HTTPException(
            status_code=404,
            detail="Guided session not found.",
        )

    return record


def _save_session_record(
    db,
    record,
    session: dict,
) -> None:
    """Persist working session state back onto its own row."""

    record.steps_json = json.dumps(
        session.get("steps", []),
        ensure_ascii=False,
    )

    record.current_step_index = int(
        session.get(
            "current_step_index",
            0,
        )
    )

    record.total_steps = len(
        session.get("steps", [])
    )

    record.all_completed = bool(
        session.get(
            "all_completed",
            False,
        )
    )

    if (
        record.all_completed
        and record.completed_at is None
    ):
        record.completed_at = datetime.now()

    db.commit()


# ============================================================================
# RULE HELPERS
# ============================================================================

def _find_rule(
    rules: list[dict],
    rule_id,
):
    """Find a rule by ID."""

    if not rules:
        return None

    for rule in rules:

        if str(
            rule.get("id")
        ) == str(rule_id):

            return rule

    return None


# ============================================================================
# SESSION SERIALIZATION
# ============================================================================

def _serialize_session(
    session: dict,
) -> dict:

    steps = session.get(
        "steps",
        [],
    )

    total = len(steps)

    completed = sum(
        1
        for step in steps
        if step.get("status") == "completed"
    )

    active_idx = session.get(
        "current_step_index",
        0,
    )

    active = (
        steps[active_idx]
        if 0 <= active_idx < total
        else None
    )

    return {
        "session_id": session.get(
            "session_id"
        ),

        "total_steps": total,

        "completed_steps": completed,

        "current_step_index": active_idx,

        "all_completed": session.get(
            "all_completed",
            False,
        ),

        "progress": (
            round(
                (completed / total) * 100
            )
            if total
            else 0
        ),

        # The rule's description, expected outcome and constraints stay
        # server-side. The client gets the step's identity, what to
        # provide, and the example — nothing that restates the rule.

        "active_rule": (
            {
                "rule_id": active.get(
                    "rule_id"
                ),

                "rule_name": active.get(
                    "rule_name"
                ),

                "what_to_provide": (
                    presenter.what_to_provide(
                        active
                    )
                ),

                "suggested_example": active.get(
                    "suggested_example",
                    "",
                ),

                "example_source": active.get(
                    "example_source",
                    "",
                ),
            }
            if active
            else None
        ),

        # Allowlisted per step — see step_presenter._PUBLIC_STEP_FIELDS.

        "steps": [
            presenter.public_step(step)
            for step in steps
        ],
    }


# ============================================================================
# ROUTE USER MESSAGE
# ============================================================================

def route_user_message(
    db,
    *,
    run_id: int,
    user_message: str,
    rules: list[dict] | None = None,
) -> dict:

    from app.db.models import SkillEngineRun

    run = (
        db.query(SkillEngineRun)
        .filter(
            SkillEngineRun.id == run_id
        )
        .first()
    )

    if not run:

        raise HTTPException(
            status_code=404,
            detail="Run not found.",
        )

    if not rules:

        rules = _load_json(
            run.rules_json,
            [],
        )

    if not rules:

        raise HTTPException(
            status_code=400,
            detail="No rules available.",
        )

    route = route_message_to_rule(
        user_message,
        rules,
    )

    if (
        not route.get("matched")
        or route.get("rule_id") is None
    ):

        # Step names only. Listing each rule's task here would hand
        # the user the rule set they are supposed to be walked through.

        listing = "\n".join(
            _esc(
                f"- {rule.get('name') or f'Step {index}'}"
            )
            for index, rule in enumerate(
                rules,
                start=1,
            )
        )

        return {
            "run_id": run_id,
            "matched_rule": None,
            "matched": False,
            "reason": route.get(
                "reason",
                "",
            ),
            "ai_response": (
                "I couldn't tell which step you meant.\n\n"
                "Steps in this task:\n\n"
                f"{listing}"
            ),
        }

    rule = _find_rule(
        rules,
        route.get("rule_id"),
    )

    if not rule:

        return {
            "run_id": run_id,
            "matched_rule": None,
            "matched": False,
            "reason": "Routed rule could not be resolved.",
            "ai_response": (
                "I couldn't resolve the routed rule."
            ),
        }

    metadata = _load_run_metadata(
        run
    )

    previous_verdict = next(
        (
            result
            for result in metadata.get(
                "results",
                [],
            )
            if str(
                result.get("rule_id")
            )
            == str(
                rule.get("id")
            )
        ),
        None,
    )

    response = run_rule_followup(
        rule=rule,
        user_message=user_message,
        conversation_history=[],
        previous_verdict=previous_verdict,
    )

    return {
        "run_id": run_id,

        # Identity only — the rule's task and expected outcome define
        # how the value is judged and stay server side.

        "matched_rule": {
            "rule_id": rule.get("id"),

            "rule_name": rule.get(
                "name"
            ),
        },

        "matched": True,

        "reason": route.get(
            "reason",
            "",
        ),

        "ai_response": response,
    }


# ============================================================================
# INITIALIZE GUIDED SESSION
# ============================================================================

def init_guided_session(
    db,
    *,
    run_id: int,
    user_id: int | None = None,
    rules: list[dict] | None = None,
) -> dict:

    from app.db.models import GuidedSession, SkillEngineRun

    run = (
        db.query(SkillEngineRun)
        .filter(
            SkillEngineRun.id == run_id
        )
        .first()
    )

    if not run:

        raise HTTPException(
            status_code=404,
            detail="Run not found.",
        )

    if (
        user_id is not None
        and run.user_id != user_id
    ):

        raise HTTPException(
            status_code=404,
            detail="Run not found.",
        )

    if not rules:

        rules = _load_json(
            run.rules_json,
            [],
        )

    if not rules:

        raise HTTPException(
            status_code=400,
            detail="No rules available for guided session.",
        )

    # ------------------------------------------------------------
    # CREATE ALL STEPS
    # ------------------------------------------------------------

    steps = engine.build_steps(rules)

    # ------------------------------------------------------------
    # CREATE SESSION
    # ------------------------------------------------------------

    session = {
        "session_id": uuid.uuid4().hex[:12],

        "steps": steps,

        "current_step_index": 0,

        "total_steps": len(steps),

        "started_at": datetime.now().isoformat(),

        "completed_at": None,

        "all_completed": False,
    }

    # ------------------------------------------------------------
    # GENERATE EXAMPLE FOR FIRST RULE
    # ------------------------------------------------------------

    engine.prepare_example(
        steps[0],
        rules[0],
        force_new=True,
    )

    engine.ensure_collection_started(steps[0])

    # ------------------------------------------------------------
    # SAVE SESSION
    #
    # Its own row — the run's results_json is left untouched.
    # ------------------------------------------------------------

    record = GuidedSession(
        session_id=session["session_id"],
        run_id=run_id,
        user_id=(
            user_id
            if user_id is not None
            else run.user_id
        ),
        current_step_index=0,
        total_steps=len(steps),
        all_completed=False,
        steps_json=json.dumps(
            steps,
            ensure_ascii=False,
        ),
    )

    db.add(record)
    db.commit()

    # ------------------------------------------------------------
    # INITIAL RESPONSE
    # ------------------------------------------------------------

    return {
        "session": _serialize_session(
            session
        ),

        "initial_message": _build_step_message(
            session,
            steps[0],
        ),
    }


# ============================================================================
# PROCESS GUIDED INPUT
# ============================================================================

def process_guided_input(
    db,
    *,
    session_id: str,
    user_input: str,
    user_id: int | None = None,
) -> dict:

    from app.db.models import SkillEngineRun

    # ------------------------------------------------------------
    # 1. LOAD SESSION
    #
    # Direct lookup by session_id; the run follows from the session.
    # ------------------------------------------------------------

    record = _load_session_record(
        db,
        session_id=session_id,
        user_id=user_id,
    )

    session = _session_to_dict(record)

    # ------------------------------------------------------------
    # 2. LOAD RUN
    # ------------------------------------------------------------

    run = (
        db.query(SkillEngineRun)
        .filter(
            SkillEngineRun.id == record.run_id
        )
        .first()
    )

    if not run:

        raise HTTPException(
            status_code=404,
            detail="Run not found.",
        )

    # ------------------------------------------------------------
    # 3. ALREADY COMPLETE
    # ------------------------------------------------------------

    if session.get(
        "all_completed"
    ):

        return {
            "session_id": session_id,

            "all_completed": True,

            "ai_response": (
                "All rules have been satisfied. "
                "Great work!"
            ),

            "session": _serialize_session(
                session
            ),
        }

    # ------------------------------------------------------------
    # 4. GET CURRENT STEP
    # ------------------------------------------------------------

    steps = session.get(
        "steps",
        [],
    )

    current_idx = session.get(
        "current_step_index",
        0,
    )

    total = len(steps)

    if not steps:

        raise HTTPException(
            status_code=400,
            detail="Guided session contains no rules.",
        )

    if current_idx >= total:

        session["all_completed"] = True

        session["completed_at"] = (
            datetime.now().isoformat()
        )

        _save_session_record(
            db,
            record,
            session,
        )

        return {
            "session_id": session_id,

            "all_completed": True,

            "ai_response": (
                "All rules have been satisfied."
            ),

            "session": _serialize_session(
                session
            ),
        }

    # ------------------------------------------------------------
    # 5. CURRENT STEP
    # ------------------------------------------------------------

    current_step = steps[current_idx]

    # ------------------------------------------------------------
    # 6. LOAD ORIGINAL RULES
    # ------------------------------------------------------------

    rules = _load_json(
        run.rules_json,
        [],
    )

    # ------------------------------------------------------------
    # 7. RUN ONE TURN OF THE WALKTHROUGH
    #
    # Judging, advancing and wording all live in guided_engine, which
    # step_by_step_service drives too. This service only persists the
    # outcome and renders it.
    # ------------------------------------------------------------

    turn = engine.take_turn(
        steps=steps,
        current_index=current_idx,
        rules=rules,
        user_input=user_input,
    )

    verdict = turn["verdict"]

    engine.record_exchange(
        current_step,
        user_input,
        " ".join(turn["message_lines"][:2]),
    )

    session["current_step_index"] = turn["current_index"]

    session["all_completed"] = turn["all_completed"]

    if turn["all_completed"]:
        session["completed_at"] = datetime.now().isoformat()

    # ------------------------------------------------------------
    # 10. RENDER
    #
    # The engine decided what to say; this service only styles it.
    # The step whose example card is shown is the one the user is on
    # after the turn — the next step when they advanced, the same
    # step when they did not.
    # ------------------------------------------------------------

    focus_step = turn["next_step"] or current_step

    focus_index = turn["current_index"]

    ai_response = _html_message(turn["message_blocks"])

    if not turn["all_completed"]:

        ai_response += (
            "<br><br>"
            + _build_summary_html(
                focus_step,
                focus_index,
                total,
                suggested_fix=str(
                    focus_step.get("suggested_example") or ""
                ),
            )
        )

    # ------------------------------------------------------------
    # 12. SAVE SESSION
    # ------------------------------------------------------------

    _save_session_record(
        db,
        record,
        session,
    )

    # ------------------------------------------------------------
    # 13. RETURN
    # ------------------------------------------------------------

    return {
        "session_id": session_id,

        # The step this response is about...
        "step_index": current_idx,

        "step_name": presenter.step_label(current_step),

        # ...and where the user stands after it.
        "current_step_index": turn["current_index"],

        "status": verdict.get(
            "status",
        ),

        "passed": turn["passed"],

        "ai_response": ai_response,

        # Outcome plus corrective feedback only. The full verdict
        # carries the rule's constraints and guidance and stays server
        # side — see step_presenter.public_verdict().

        "verdict": turn["public_verdict"],

        # The example for the step the user is on now.

        "suggested_example": str(
            focus_step.get("suggested_example") or ""
        ),

        "example_source": str(
            focus_step.get("example_source") or ""
        ),

        "session": _serialize_session(
            session
        ),

        "all_completed": session.get(
            "all_completed",
            False,
        ),
    }


# ============================================================================
# GET GUIDED SESSION
# ============================================================================

def get_guided_session(
    db,
    *,
    session_id: str,
    user_id: int | None = None,
) -> dict:

    record = _load_session_record(
        db,
        session_id=session_id,
        user_id=user_id,
    )

    return {
        "session": _serialize_session(
            _session_to_dict(record)
        )
    }


# ============================================================================
# EDITING AN ALREADY-COMPLETED STEP
# ============================================================================

def list_completed_steps(
    db,
    *,
    session_id: str,
    user_id: int | None = None,
) -> dict:
    """
    Completed steps of a guided session, with what the user submitted
    for each — the "editing mode" source list.
    """

    record = _load_session_record(
        db,
        session_id=session_id,
        user_id=user_id,
    )

    session = _session_to_dict(record)

    steps = session.get("steps", [])

    return {
        "session_id": session_id,
        "steps": [
            composite_rules.completed_step_preview(step)
            for step in steps
            if step.get("status") == "completed"
        ],
    }


def edit_guided_step(
    db,
    *,
    session_id: str,
    step_index: int,
    user_input: str,
    user_id: int | None = None,
) -> dict:
    """
    Correct the answer already submitted for a completed step of a
    guided session.

    Unlike process_guided_input, this never touches
    current_step_index or all_completed — the user resumes exactly
    where they were once the correction is judged.
    """

    from app.db.models import SkillEngineRun

    record = _load_session_record(
        db,
        session_id=session_id,
        user_id=user_id,
    )

    session = _session_to_dict(record)

    steps = session.get("steps", [])

    run = (
        db.query(SkillEngineRun)
        .filter(
            SkillEngineRun.id == record.run_id
        )
        .first()
    )

    if not run:

        raise HTTPException(
            status_code=404,
            detail="Run not found.",
        )

    rules = _load_json(
        run.rules_json,
        [],
    )

    if (
        not (0 <= step_index < len(steps))
        or steps[step_index].get("status") != "completed"
    ):

        raise HTTPException(
            status_code=400,
            detail="That step cannot be edited right now.",
        )

    result = engine.edit_completed_step(
        steps=steps,
        edit_index=step_index,
        rules=rules,
        user_input=user_input,
    )

    # current_step_index / all_completed are carried over from the
    # session exactly as loaded — an edit never advances or rewinds
    # the walkthrough.
    session["steps"] = steps

    _save_session_record(
        db,
        record,
        session,
    )

    return {
        "session_id": session_id,
        "step_index": step_index,
        "edited": result["edited"],
        "ai_response": _html_message(result["message_blocks"]),
        "verdict": result["public_verdict"],
        "session": _serialize_session(session),
    }


# ============================================================================
# STEP COLOR
# ============================================================================

def _step_color(
    index: int,
) -> str:

    return _STEP_BG_COLOR


# ============================================================================
# EXAMPLE HTML
# ============================================================================

def _build_example_html(
    step: dict,
    suggested_fix: str = "",
    step_index: int = 0,
) -> str:

    # The value itself, not a sentence wrapped around it. This used to
    # build "Give me the corresponding input, e.g., X" and then strip
    # the prefix back off here.

    clean = html.escape(
        str(
            suggested_fix
            or step.get("suggested_example")
            or engine.prepare_example(step)
            or ""
        ).strip()
    )

    color = _step_color(
        step_index
    )

    return (
        f"<div style='"
        f"margin-top:12px;"
        f"padding:10px 12px;"
        f"border-radius:8px;"
        f"background:linear-gradient("
        f"135deg,#eef2ff 0%,#e0e7ff 100%);"
        f"border:1px solid #c7d2fe;"
        f"border-left:4px solid {color};"
        f"'>"

        f"<div style='"
        f"font-size:11px;"
        f"font-weight:700;"
        f"color:#4338ca;"
        f"text-transform:uppercase;"
        f"letter-spacing:0.5px;"
        f"margin-bottom:4px;"
        f"'>"
        f"Example Input"
        f"</div>"

        f"<div style='"
        f"font-size:13px;"
        f"color:#1e1b4b;"
        f"font-family:Consolas,monospace;"
        f"font-weight:600;"
        f"white-space:pre-wrap;"
        f"'>"
        f"{clean}"
        f"</div>"

        f"</div>"
    )


# ============================================================================
# SUMMARY HTML
# ============================================================================

def _build_summary_html(
    step: dict,
    step_index: int,
    total: int,
    suggested_fix: str = "",
) -> str:

    color = _step_color(
        step_index
    )

    heading = _esc(
        presenter.step_heading(
            step,
            step_index,
            total,
        )
    )

    badge = (
        f"<div style='"
        f"display:inline-block;"
        f"padding:6px 14px;"
        f"border-radius:8px;"
        f"background-color:{color};"
        f"color:#ffffff;"
        f"font-weight:700;"
        f"text-transform:uppercase;"
        f"font-size:13px;"
        f"letter-spacing:0.5px;"
        f"'>"

        f"{heading}"

        f"</div>"
    )

    # What to provide, in place of the rule that defines it.

    instruction = (
        f"<p style='"
        f"margin:8px 0 0 0;"
        f"color:#475569;"
        f"font-size:13px;"
        f"'>"
        f"{_esc(presenter.what_to_provide(step))}"
        f"</p>"
    )

    box = _build_example_html(
        step,
        suggested_fix=suggested_fix,
        step_index=step_index,
    )

    return (
        badge
        + instruction
        + box
    )


# ============================================================================
# INITIAL STEP MESSAGE
# ============================================================================

_WELCOME_PREAMBLE = (
    "<p style='"
    "margin:0 0 8px 0;"
    "color:#64748b;"
    "font-size:13px;"
    "'>"
    "Welcome to the guided walkthrough"
    "</p>"
)


def _build_step_message(
    session: dict,
    step: dict,
) -> str:

    current_idx = session.get(
        "current_step_index",
        0,
    )

    total = len(
        session.get("steps", [])
    )

    # A composite (table/list) step is filled one field at a time —
    # delegate to the shared presenter rather than this bespoke
    # badge/example-box renderer, which only knows how to introduce a
    # step as a single whole-answer prompt. Scalar steps keep today's
    # look untouched, so this cannot regress the working, common case.

    if composite_rules.input_shape(step) in composite_rules.COMPOSITE_SHAPES:
        return _WELCOME_PREAMBLE + _html_message(
            presenter.build_step_prompt(step, current_idx, total)
        )

    badge_color = _step_color(
        current_idx
    )

    suggested_example = str(
        step.get(
            "suggested_example",
            "",
        )
        or ""
    ).strip()

    example_html = _build_example_html(
        step,
        suggested_fix=suggested_example,
        step_index=current_idx,
    )

    heading = _esc(
        presenter.step_heading(
            step,
            current_idx,
            total,
        )
    )

    # What to provide — NOT the rule behind it.

    instruction = _esc(
        presenter.what_to_provide(step)
    )

    return (
        _WELCOME_PREAMBLE

        + f"<div style='"
        f"display:inline-block;"
        f"padding:6px 14px;"
        f"border-radius:8px;"
        f"background-color:{badge_color};"
        f"color:#ffffff;"
        f"font-weight:700;"
        f"text-transform:uppercase;"
        f"font-size:13px;"
        f"letter-spacing:0.5px;"
        f"'>"

        f"{heading}"

        f"</div>"

        f"<p style='"
        f"margin:10px 0 0 0;"
        f"color:#475569;"
        f"font-size:13px;"
        f"'>"

        f"{instruction}"

        f"</p>"

        f"{example_html}"
    )


