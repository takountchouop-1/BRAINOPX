"""
step_presenter.py

The only place that builds what the user sees during a guided walkthrough.

The user is shown exactly this and nothing else:

    - the current step
    - what they need to provide
    - an example input
    - whether their input was accepted
    - what is missing or incorrect
    - a corrected example when their input failed
    - the next step once a step is accepted

Internal rule definitions stay hidden. Rule descriptions, tasks,
expected outcomes, constraint dictionaries, keywords, semantic types,
match patterns and raw validator payloads are used to decide whether a
value is correct, but they are never rendered and never serialized into
an API response.

Everything leaving this module works from an allowlist: fields are
copied out by name, so a new internal field added to a step or verdict
upstream cannot leak by default.
"""

import html
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# WHAT THE USER MAY SEE
# ============================================================

# Step fields safe to send to the client.
_PUBLIC_STEP_FIELDS = (
    "step_index",
    "rule_id",
    "rule_name",
    "status",
    "attempts",
    "suggested_example",
    # Where suggested_example came from: "rule" (precomputed/uploaded),
    # "ai" (Groq), "builder" (deterministic generator), or "none". Lets
    # a caller tell a real AI-generated example from an offline one.
    "example_source",
    # Plain-language description of the general format the example
    # follows (Groq-generated only). Lets the user construct their own
    # valid values instead of only copying the one example shown.
    "example_explanation",
)

# Verdict fields safe to send to the client. Notably absent:
# constraints, guidance, example_validation, validation, questions,
# next_action — all of which describe the rule rather than the answer.
_PUBLIC_VERDICT_FIELDS = (
    "status",
    "passed",
)

_GENERIC_PROBLEM = (
    "The value entered is not in the expected format."
)


# ============================================================
# MESSAGE ROLES
# ============================================================

# What each line of a message is, so every caller can style it the
# same way. Without this only the first step was styled: later
# messages were rendered as undifferentiated text.

ROLE_HEADING = "heading"            # "Step 2 of 8: Unit Rate"
ROLE_INSTRUCTION = "instruction"    # "Enter the Unit Rate."
ROLE_EXAMPLE = "example"            # the sample value itself
ROLE_PROBLEM = "problem"            # what is missing or incorrect
ROLE_CONFIRMATION = "confirmation"  # "Unit Rate accepted."
ROLE_TEXT = "text"                  # anything else

# A rendered <table>. Unlike every other role, its text is markup
# rather than plain text, and renderers must NOT escape it again —
# composite_rules.render_table_html escapes each cell as it places
# it, so the markup is already safe. Nothing else may use this role.
ROLE_TABLE = "table"


def block(role: str, text: str) -> dict:
    """One line of a message, with what it is."""

    return {"role": role, "text": text}


def lines_of(blocks) -> list[str]:
    """The plain text of a block list."""

    return [
        str(item.get("text", ""))
        if isinstance(item, dict)
        else str(item)
        for item in (blocks or [])
    ]

# Cap how many problems are listed, so a value failing many internal
# checks does not let the user reconstruct the rule from the feedback.
_MAX_PROBLEMS = 2


# ============================================================
# HELPERS
# ============================================================

def _esc(value, default: str = "") -> str:
    """Escape a value for a response rendered via innerHTML."""

    text = str(
        value
        if value is not None
        else ""
    ).strip()

    return html.escape(
        text or default
    )


def _clean(value, default: str = "") -> str:
    """Plain (unescaped) text, trimmed."""

    text = str(
        value
        if value is not None
        else ""
    ).strip()

    return text or default


def step_label(step: dict) -> str:
    """
    The step's display name.

    Accepts either shape in use: guided steps carry `rule_name`, raw
    rules carry `name`.
    """

    if not isinstance(step, dict):
        return "This step"

    return _clean(
        step.get("rule_name")
        or step.get("name"),
        "This step",
    )


def what_to_provide(step: dict) -> str:
    """
    One line telling the user what this step wants.

    Derived from the step's label and its input shape. The rule's
    description and expected outcome are deliberately not used — the
    example carries the required format, without restating the rule.

    A list or table step also states how to lay the answer out, and
    names the columns: a user cannot fill a table without knowing its
    columns. What makes a cell valid stays hidden.
    """

    label = step_label(step)

    from app.services import composite_rules

    layout = composite_rules.describe_expected_input(step)

    if layout:
        if label.lower() in ("this step", ""):
            return layout
        return f"Enter the {label}. {layout}"

    if label.lower() in ("this step", ""):
        return "Enter the value for this step."

    return f"Enter the {label}."


def example_for(step: dict, fallback: str = "") -> str:
    """The example input already prepared for this step."""

    return _clean(
        step.get("suggested_example"),
        _clean(fallback),
    )


def explanation_for(step: dict) -> str:
    """
    Plain-language description of the general format the current
    example follows, so the user can build their own valid values
    rather than only copying the one example shown. Empty unless the
    example came from the AI, which is the only source that produces
    this.
    """

    return _clean(step.get("example_explanation"))


def problems_from(verdict: dict, limit: Optional[int] = None) -> list[str]:
    """
    Turn a verdict into the short list of things wrong with the value.

    Reads only the validator's plain-language errors. The rule text
    that produced them is not consulted.

    A list or table answer raises the cap through `problem_limit`:
    being told two of six bad cells would mean six round trips to fix
    one paste, and a per-cell message names a row, not the rule.
    """

    if not isinstance(verdict, dict):
        return [_GENERIC_PROBLEM]

    raw = verdict.get("validation_errors")

    validation = verdict.get("validation")

    if not isinstance(raw, list):
        raw = (
            validation.get("errors")
            if isinstance(validation, dict)
            else None
        )

    if limit is None:
        limit = _MAX_PROBLEMS

        for source in (verdict, validation):
            if isinstance(source, dict) and source.get("problem_limit"):
                try:
                    limit = max(limit, int(source["problem_limit"]))
                except (TypeError, ValueError):
                    pass

    problems = []

    if isinstance(raw, list):
        for item in raw:
            text = _clean(item)
            if text and text not in problems:
                problems.append(text)

    if not problems:
        reason = _clean(
            verdict.get("validation_reason")
        )
        if reason:
            problems.append(reason)

    if not problems:
        problems.append(_GENERIC_PROBLEM)

    return problems[:limit]


# ============================================================
# SANITIZED API PAYLOADS
# ============================================================

def has_specific_problem(verdict: dict) -> bool:
    """
    Whether the validator said something actionable about the value.

    Generic complaints — that it is a placeholder, or that it does
    not look meaningful — say nothing the user can act on. A concrete
    one ("must be a valid number", "must start with TRF") does.
    """

    vague = (
        "generic placeholder",
        "appears to be invalid",
    )

    for problem in problems_from(verdict, limit=10):

        lowered = problem.lower()

        if lowered == _GENERIC_PROBLEM.lower():
            continue

        if any(phrase in lowered for phrase in vague):
            continue

        return True

    return False


def public_step(step: dict) -> dict:
    """A step, reduced to the fields the client may hold."""

    if not isinstance(step, dict):
        return {}

    return {
        field: step.get(field)
        for field in _PUBLIC_STEP_FIELDS
    }


def public_verdict(verdict: dict) -> dict:
    """
    A verdict, reduced to the outcome plus the corrective feedback.

    The rule that produced the outcome does not travel with it.
    """

    if not isinstance(verdict, dict):
        return {
            "status": "failed",
            "passed": False,
            "problems": [_GENERIC_PROBLEM],
        }

    result = {
        field: verdict.get(field)
        for field in _PUBLIC_VERDICT_FIELDS
    }

    if not verdict.get("passed"):
        result["problems"] = problems_from(verdict)

    return result


# ============================================================
# MESSAGES
# ============================================================

def step_heading(
    step: dict,
    step_index: int,
    total: int,
) -> str:
    """`Step 2 of 4: Unit Rate`"""

    return (
        f"Step {step_index + 1} of {total}: "
        f"{step_label(step)}"
    )


# ============================================================
# FIELD-BY-FIELD COLLECTION (table/list steps)
# ============================================================

def _table_collection_prompt(
    step: dict,
    step_index: int,
    total: int,
    progress: dict,
) -> list[dict]:

    from app.services import composite_rules
    from app.services.example_utils import build_example_value

    columns = composite_rules.columns_of(step)
    row_number = progress.get("row_index", 0) + 1

    if progress.get("stage") == "row_decision":

        rows = progress.get("rows", [])

        blocks = [
            block(ROLE_CONFIRMATION, f"Row {row_number} added."),
        ]

        rendered = composite_rules.render_table_html(columns, rows)

        if rendered:
            blocks.append(block(ROLE_TABLE, rendered))

        blocks.append(
            block(
                ROLE_INSTRUCTION,
                "Type 'add' to enter another row, "
                "or 'done' if this is all the rows.",
            )
        )

        return blocks

    column_index = progress.get("column_index", 0)
    column = columns[column_index] if column_index < len(columns) else None
    column_name = column.get("name") if column else "value"

    blocks = []

    if row_number == 1 and column_index == 0:
        blocks.append(block(ROLE_HEADING, step_heading(step, step_index, total)))
        blocks.append(
            block(
                ROLE_INSTRUCTION,
                f"Enter the {step_label(step)}, one field at a time.",
            )
        )

    blocks.append(block(ROLE_INSTRUCTION, f"Row {row_number} — {column_name}:"))

    if column:
        try:
            sample = _clean(build_example_value(column))
        except Exception:
            sample = ""

        if sample:
            blocks.append(block(ROLE_EXAMPLE, f"Example: {sample}"))

    return blocks


def _list_collection_prompt(
    step: dict,
    step_index: int,
    total: int,
    progress: dict,
) -> list[dict]:

    from app.services import composite_rules
    from app.services.example_utils import build_example_value

    items = progress.get("items", [])
    item_number = len(items) + 1
    minimum = composite_rules.minimum_items(step)
    item_rule = composite_rules.item_rule_of(step)

    blocks = []

    if item_number == 1:
        blocks.append(block(ROLE_HEADING, step_heading(step, step_index, total)))
        blocks.append(
            block(
                ROLE_INSTRUCTION,
                f"Enter the {step_label(step)}, one item at a time.",
            )
        )

    blocks.append(block(ROLE_INSTRUCTION, f"Item {item_number}:"))

    try:
        sample = _clean(build_example_value(item_rule))
    except Exception:
        sample = ""

    if sample:
        blocks.append(block(ROLE_EXAMPLE, f"Example: {sample}"))

    if len(items) >= minimum:
        blocks.append(
            block(ROLE_TEXT, "Type 'done' when you have entered all items.")
        )

    return blocks


def build_collection_prompt(
    step: dict,
    step_index: int,
    total: int,
) -> list[dict]:
    """
    The next sub-prompt of a table/list step being filled one field
    at a time, read from step["composite_progress"].
    """

    progress = step.get("composite_progress") or {}
    shape = progress.get("shape")

    if shape == "table":
        return _table_collection_prompt(step, step_index, total, progress)

    if shape == "list":
        return _list_collection_prompt(step, step_index, total, progress)

    # No recognised collection in progress — fall back to a plain
    # heading/instruction rather than recursing into build_step_prompt.
    return [
        block(ROLE_HEADING, step_heading(step, step_index, total)),
        block(ROLE_INSTRUCTION, what_to_provide(step)),
    ]


def build_field_problem_message(
    step: dict,
    step_index: int,
    total: int,
    field_label: str,
    errors: list,
) -> list[dict]:
    """
    One field of a table/list collection was rejected: what was wrong
    with just that field, then the same field asked again.
    """

    problems = [
        text
        for text in (str(error).strip() for error in (errors or []))
        if text
    ] or [_GENERIC_PROBLEM]

    problems = problems[:_MAX_PROBLEMS]

    if len(problems) == 1:
        blocks = [block(ROLE_PROBLEM, f"{field_label}: {problems[0]}")]
    else:
        blocks = [block(ROLE_PROBLEM, f"{field_label}:")]
        blocks.extend(
            block(ROLE_PROBLEM, f"- {problem}")
            for problem in problems
        )

    blocks.extend(build_collection_prompt(step, step_index, total))

    return blocks


def build_collection_shortfall_message(
    step: dict,
    step_index: int,
    total: int,
    *,
    kind: str,
    minimum: int,
    have: int,
) -> list[dict]:
    """
    The user tried to finish a table/list step before its minimum was
    met — reminded, then asked the same add/done (or item) prompt.
    """

    noun = "row" if kind == "rows" else "item"

    blocks = [
        block(
            ROLE_PROBLEM,
            f"At least {minimum} {noun}{'s' if minimum != 1 else ''} "
            f"required. You have entered {have}.",
        ),
    ]

    blocks.extend(build_collection_prompt(step, step_index, total))

    return blocks


def build_edit_success_message(
    step: dict,
    step_index: int,
    total: int,
    submitted_value: str = "",
) -> list[dict]:
    """
    Confirms a corrected answer to an already-completed step.

    Never introduces a next step — editing does not advance the
    workflow.
    """

    from app.services import composite_rules

    shape = composite_rules.input_shape(step)

    label_line = f"{step_label(step)} updated."

    if shape not in composite_rules.COMPOSITE_SHAPES and _clean(submitted_value):
        label_line = f'{step_label(step)} updated: "{_clean(submitted_value)}"'

    blocks = [block(ROLE_CONFIRMATION, label_line)]

    if shape == composite_rules.SHAPE_TABLE:
        rendered = composite_rules.render_submitted_table(step, submitted_value, {})
        if rendered:
            blocks.append(block(ROLE_TABLE, rendered))

    elif shape == composite_rules.SHAPE_LIST:
        items = composite_rules.parse_items(submitted_value)
        rendered = composite_rules.render_list_html(items, caption="What you entered")
        if rendered:
            blocks.append(block(ROLE_TABLE, rendered))

    return blocks


def build_step_prompt(
    step: dict,
    step_index: int,
    total: int,
    example: str = "",
) -> list[dict]:
    """
    Blocks introducing a step: what it is, what to provide, an example.

    A table/list step whose field-by-field collection is already under
    way shows its current sub-prompt instead — this is what lets every
    call site (advancing to a composite next step, a task's very first
    composite rule) get the field-by-field flow automatically, with no
    special-casing of its own.
    """

    progress = step.get("composite_progress")

    if isinstance(progress, dict) and progress.get("active"):
        return build_collection_prompt(step, step_index, total)

    blocks = [
        block(ROLE_HEADING, step_heading(step, step_index, total)),
        block(ROLE_INSTRUCTION, what_to_provide(step)),
    ]

    from app.services import composite_rules

    # A table step shows its example as a table. Comma-separated
    # lines are hard to line up against the column names.

    if composite_rules.input_shape(step) == composite_rules.SHAPE_TABLE:

        rendered = composite_rules.render_example_table(step)

        if rendered:
            blocks.append(block(ROLE_TEXT, "Example input:"))
            blocks.append(block(ROLE_TABLE, rendered))
            return blocks

    value = example_for(step, example)

    if value:
        blocks.append(block(ROLE_EXAMPLE, f"Example input: {value}"))

        explanation = explanation_for(step)

        if explanation:
            blocks.append(block(ROLE_TEXT, f"Format: {explanation}"))

    elif step.get("example_source") == "ai_unavailable":
        blocks.append(
            block(
                ROLE_PROBLEM,
                "The AI service could not generate an example for "
                "this step right now. You can still enter a value — "
                "it will be checked against the rule as usual.",
            )
        )

    return blocks


def build_failure_message(
    step: dict,
    step_index: int,
    total: int,
    verdict: dict,
    corrected_example: str = "",
    learned_hint: str = "",
    submitted_value: str = "",
) -> list[dict]:
    """
    Blocks for a rejected value.

    What was wrong, optionally what previous users did to recover,
    then a corrected example, then an invitation to
    try the same step again.
    """

    label = step_label(step)

    blocks = [
        block(
            ROLE_HEADING,
            f"{step_heading(step, step_index, total)} — not accepted",
        ),
    ]

    # Show a table step's rows back with the failing cells marked, so
    # the user can see which value to fix rather than matching
    # "Row 2, Unit Rate" against what they typed.

    from app.services import composite_rules

    if composite_rules.input_shape(step) == composite_rules.SHAPE_TABLE:

        submitted = composite_rules.render_submitted_table(
            step,
            str(submitted_value or ""),
            verdict,
        )

        if submitted:
            blocks.append(block(ROLE_TABLE, submitted))

    elif _clean(submitted_value):
        # Quotes the value back so the problem below reads against
        # what was actually typed, not just against the rule.
        blocks.append(
            block(ROLE_TEXT, f'You entered: "{_clean(submitted_value)}"')
        )

    problems = problems_from(verdict)

    if len(problems) == 1:
        blocks.append(
            block(ROLE_PROBLEM, f"What is missing: {problems[0]}")
        )
    else:
        blocks.append(block(ROLE_PROBLEM, "What is missing:"))
        blocks.extend(
            block(ROLE_PROBLEM, f"- {problem}")
            for problem in problems
        )

    # What previous users did to get past this same error. Offered
    # before the generated example, since it is evidence of something
    # that actually worked here.

    hint = _clean(learned_hint)

    value = example_for(step, corrected_example)

    if hint and hint != value:
        blocks.append(
            block(
                ROLE_TEXT,
                f"Others got past this by entering: {hint}",
            )
        )

    if composite_rules.input_shape(step) == composite_rules.SHAPE_TABLE:

        corrected = composite_rules.render_example_table(step)

        if corrected:
            blocks.append(block(ROLE_TEXT, "Use this layout instead:"))
            blocks.append(block(ROLE_TABLE, corrected))
            blocks.append(
                block(ROLE_INSTRUCTION, f"Please enter the {label} again.")
            )
            return blocks

    if value:
        blocks.append(
            block(ROLE_EXAMPLE, f"Use this format instead: {value}")
        )

    blocks.append(
        block(ROLE_INSTRUCTION, f"Please enter the {label} again.")
    )

    return blocks


def build_warning_message(
    step: dict,
    step_index: int,
    total: int,
    warning_reason: str,
    example: str = "",
) -> list[dict]:
    """
    Blocks for a value that is hard-valid but risky.

    Explains the risk, then asks the user to explicitly accept or
    decline — the step does not advance until they answer either way.
    """

    label = step_label(step)

    blocks = [
        block(
            ROLE_HEADING,
            f"{step_heading(step, step_index, total)} — accepted with a warning",
        ),
    ]

    if _clean(example):
        blocks.append(block(ROLE_TEXT, f'You entered: "{_clean(example)}"'))

    reason = _clean(warning_reason) or (
        "This value is unusual — please confirm before continuing."
    )
    blocks.append(block(ROLE_PROBLEM, reason))

    blocks.append(
        block(
            ROLE_INSTRUCTION,
            f"Type 'yes' to continue with this {label} anyway, "
            "or 'no' to enter a different value.",
        )
    )

    return blocks


def build_warning_declined_message(
    step: dict,
    step_index: int,
    total: int,
    example: str = "",
) -> list[dict]:
    """
    Blocks after the user declines a WARNING.

    The declined value was not wrong — build_failure_message's "what
    is missing" framing does not apply — so this simply confirms it
    was set aside and re-prompts for a different one.
    """

    blocks = [
        block(
            ROLE_CONFIRMATION,
            "That value was not used. Let's try a different one.",
        ),
    ]

    blocks.extend(build_step_prompt(step, step_index, total, example))

    return blocks


def build_need_more_info_message(
    step: dict,
    step_index: int,
    total: int,
    missing_topics: list,
) -> list[dict]:
    """
    Blocks asking for exactly what a hard-valid answer still needs to
    cover. The step stays at the SAME position — this is not a
    rejection, so what the user already wrote is not discarded.
    """

    blocks = [
        block(ROLE_HEADING, step_heading(step, step_index, total)),
    ]

    topics = [
        str(topic).strip()
        for topic in (missing_topics or [])
        if str(topic).strip()
    ]

    if len(topics) == 1:
        blocks.append(
            block(
                ROLE_PROBLEM,
                f"Almost there — please also address: {topics[0]}",
            )
        )
    elif topics:
        blocks.append(block(ROLE_PROBLEM, "Almost there — please also address:"))
        blocks.extend(
            block(ROLE_PROBLEM, f"- {topic}")
            for topic in topics
        )
    else:
        blocks.append(
            block(
                ROLE_PROBLEM,
                "A little more detail is needed before this can be accepted.",
            )
        )

    blocks.append(
        block(
            ROLE_INSTRUCTION,
            "You can add to what you already wrote — no need to start over.",
        )
    )

    return blocks


def build_success_message(
    step: dict,
    step_index: int,
    total: int,
    next_step: dict | None = None,
    next_example: str = "",
    submitted_value: str = "",
) -> list[str]:
    """
    Lines confirming a step, then introducing the next one.

    A composite step's accepted answer is shown back assembled as a
    table (or a one-column list), so the confirmation reads the way
    the step was filled in rather than as a raw separated blob.
    """

    from app.services import composite_rules

    shape = composite_rules.input_shape(step)

    # A plain single-value step quotes back exactly what was accepted,
    # rather than just confirming the step name — the user can see the
    # response is about the value they typed, not a generic pass.
    label_line = f"{step_label(step)} accepted."

    if shape not in composite_rules.COMPOSITE_SHAPES and _clean(submitted_value):
        label_line = f'{step_label(step)} accepted: "{_clean(submitted_value)}"'

    blocks = [block(ROLE_CONFIRMATION, label_line)]

    if shape == composite_rules.SHAPE_TABLE:
        rendered = composite_rules.render_submitted_table(step, submitted_value, {})
        if rendered:
            blocks.append(block(ROLE_TABLE, rendered))

    elif shape == composite_rules.SHAPE_LIST:
        items = composite_rules.parse_items(submitted_value)
        rendered = composite_rules.render_list_html(items, caption="What you entered")
        if rendered:
            blocks.append(block(ROLE_TABLE, rendered))

    if next_step is not None:
        blocks.extend(
            build_step_prompt(
                next_step,
                step_index + 1,
                total,
                next_example,
            )
        )

    return blocks


def build_all_completed_message(total: int) -> list[dict]:
    """Blocks for a finished walkthrough."""

    return [
        block(ROLE_CONFIRMATION, f"All {total} steps completed."),
        block(ROLE_TEXT, "Every value you entered was accepted."),
    ]


# ============================================================
# WHEN THE INPUT WAS NOT AN ANSWER
# ============================================================

def _step_reminder(
    step: dict,
    step_index: int,
    total: int,
    example: str = "",
) -> list[dict]:
    """What this step needs, repeated after an off-track message."""

    blocks = [
        block(ROLE_INSTRUCTION, what_to_provide(step)),
    ]

    value = example_for(step, example)

    if value:
        blocks.append(block(ROLE_EXAMPLE, f"Example input: {value}"))

        explanation = explanation_for(step)

        if explanation:
            blocks.append(block(ROLE_TEXT, f"Format: {explanation}"))

    return blocks


def build_off_track_message(
    step: dict,
    step_index: int,
    total: int,
    intent: str,
    example: str = "",
    ai_explanation: str = "",
) -> list[dict]:
    """
    Reply to input that was not an attempt at this step's value.

    Says plainly what happened — the message was not understood, or
    it asked about something out of scope — then repeats what the
    step needs. The rule behind the step is not revealed here either.

    ai_explanation, when given, is a fresh model-generated answer to a
    QUESTION_STEP — the caller (guided_engine) already scoped that call
    to this one rule, so it is shown as-is rather than replaced by the
    generic "Here is what this step needs." line.
    """

    from app.services import input_intent

    heading = step_heading(step, step_index, total)

    if intent == input_intent.EMPTY:
        opening = [
            block(ROLE_HEADING, heading),
            block(ROLE_PROBLEM, "You have not entered anything yet."),
        ]

    elif intent == input_intent.QUESTION_STEP:
        opening = [
            block(ROLE_HEADING, heading),
            block(
                ROLE_TEXT,
                ai_explanation.strip() if ai_explanation.strip() else "Here is what this step needs.",
            ),
        ]

    elif intent == input_intent.QUESTION_OTHER:
        opening = [
            block(ROLE_HEADING, heading),
            block(
                ROLE_PROBLEM,
                "I do not have information about that. I can only "
                "help you complete the steps of this task.",
            ),
        ]

    elif intent == input_intent.CHITCHAT:
        opening = [
            block(ROLE_HEADING, heading),
            block(
                ROLE_TEXT,
                "Let's carry on with the task.",
            ),
        ]

    else:  # unintelligible
        opening = [
            block(ROLE_HEADING, heading),
            block(
                ROLE_PROBLEM,
                "I did not understand that as an answer to this step.",
            ),
        ]

    return opening + _step_reminder(step, step_index, total, example)


# ============================================================
# THE AI ASKS FOR A FILE OR SCREENSHOT
#
# Reached only after several consecutive off-track turns on the same
# step (see guided_engine's confusion tracking) — a plain-language
# explanation alone has not been enough, so the user is invited to
# show, rather than describe, what they are working with.
# ============================================================

def build_request_attachment_message(
    step: dict,
    step_index: int,
    total: int,
) -> list[dict]:
    """Blocks asking the user to attach a file or screenshot."""

    return [
        block(ROLE_HEADING, step_heading(step, step_index, total)),
        block(
            ROLE_TEXT,
            "I'm having trouble making this clear from words alone. "
            "Could you attach a file or a screenshot showing what "
            "you're working with? Use the paperclip button below.",
        ),
        block(
            ROLE_INSTRUCTION,
            "Type 'skip' instead if you'd rather keep going without one.",
        ),
    ]


def build_awaiting_attachment_reminder_message(
    step: dict,
    step_index: int,
    total: int,
) -> list[dict]:
    """Repeated while a step is parked waiting for the requested attachment."""

    return [
        block(ROLE_HEADING, step_heading(step, step_index, total)),
        block(
            ROLE_TEXT,
            "Still waiting on that file or screenshot — attach it with "
            "the paperclip button, or type 'skip' to continue without one.",
        ),
    ]


def build_attachment_processed_message(
    step: dict,
    step_index: int,
    total: int,
    ai_explanation: str,
    example: str = "",
) -> list[dict]:
    """Blocks shown once the requested attachment has been read."""

    heading = step_heading(step, step_index, total)

    opening = [
        block(ROLE_HEADING, heading),
        block(
            ROLE_TEXT,
            ai_explanation.strip() if ai_explanation.strip()
            else "Thanks — I've noted that. Here is what this step needs.",
        ),
    ]

    return opening + _step_reminder(step, step_index, total, example)


def build_error_message(
    step: dict,
    step_index: int,
    total: int,
    example: str = "",
) -> list[dict]:
    """
    Reply when checking the value failed unexpectedly.

    Distinguished from a rejected value: nothing was wrong with what
    the user typed, so they are not told to correct it.
    """

    return [
        block(ROLE_HEADING, step_heading(step, step_index, total)),
        block(
            ROLE_PROBLEM,
            "I hit an error while checking that and could not "
            "complete the check. Nothing was recorded.",
        ),
        block(ROLE_INSTRUCTION, "Please send the value again."),
    ] + _step_reminder(step, step_index, total, example)


def build_network_error_message(
    step: dict,
    step_index: int,
    total: int,
    example: str = "",
) -> list[dict]:
    """
    Reply when Groq could not be reached at all (no internet, a DNS
    failure, a dropped connection) — distinguished from
    build_error_message so the user is told to check their
    connection rather than just "send it again".
    """

    return [
        block(ROLE_HEADING, step_heading(step, step_index, total)),
        block(
            ROLE_PROBLEM,
            "Please check your network and retry.",
        ),
    ] + _step_reminder(step, step_index, total, example)
