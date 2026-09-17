"""
guided_engine.py

The step machine behind every guided walkthrough.

One rule per step. For each step the user is shown an example built
from that step's own rule; the value they submit is validated against
that same rule; a correct value advances, an incorrect one stays put
with an explanation and a correction.

This module owns the decision logic only — building steps, preparing
each step's example, judging a submission, and deciding what the user
is told. It performs no I/O and knows nothing about how a walkthrough
is stored.

Two services drive it:

    rule_router_service    guided sessions on the guided_sessions table
    step_by_step_service   workflow state inside a configuration request

They differ only in persistence. Keeping the machine here is what stops
them drifting apart — previously each had its own copy, and they had
already diverged over whether the next step's example was shown at all.

User-facing wording comes from step_presenter, which is the boundary
that keeps internal rule definitions hidden.
"""

import logging
import re
from typing import Optional

from app.services.groq_service import (
    run_rule_workflow,
    run_rule_followup,
    get_chitchat_reply,
    generate_rule_example_with_retry,
    deterministic_validate_example,
    GroqNetworkError,
    MAX_RETRIES,
)

from app.services.example_utils import build_example_value

from app.services import composite_rules
from app.services import correction_memory
from app.services import input_intent
from app.services import step_presenter as presenter

logger = logging.getLogger(__name__)

# Consecutive off-track (question/confused) turns on the same step
# before the AI stops re-explaining in words and asks for a file or
# screenshot instead.
CONFUSION_THRESHOLD = 2

# Consecutive genuinely-wrong values on the same step (not off-track
# chatter) before the AI stops repeating "how to fix" and offers to
# escalate to a human instead.
MAX_FAILED_ATTEMPTS = 3


# ============================================================
# STEP CONSTRUCTION
# ============================================================

def build_step(rule: dict, index: int) -> dict:
    """
    Convert one rule into an independent step.

    Every step owns its example state, so no step can inherit the
    example generated for another.
    """

    if not isinstance(rule, dict):
        rule = {"description": str(rule or "")}

    return {
        "step_index": index,

        "rule_id": rule.get("id", index + 1),

        "rule_name": rule.get(
            "name",
            f"Rule {index + 1}",
        ),

        # Retained for validation and example generation.
        # step_presenter decides what of this the user ever sees.

        "rule_description": rule.get(
            "description",
            rule.get("task", ""),
        ),

        "task": rule.get("task", ""),

        "expected_outcome": rule.get("expected_outcome", ""),

        "data_type": rule.get("data_type", ""),

        "constraints": rule.get("constraints", {}),

        "keywords": rule.get("keywords", []),

        # Shape of the expected answer, plus the column/item rules a
        # list or table step is judged against. Carried on the step so
        # the presenter and validator see it without reloading the rule.

        "input_shape": rule.get("input_shape", ""),

        "columns": rule.get("columns", []),

        "item_rule": rule.get("item_rule", {}),

        "min_rows": rule.get("min_rows"),

        "min_items": rule.get("min_items"),

        "example": rule.get("example", ""),

        "example_input": rule.get("example_input", ""),

        "suggested_example": "",

        "example_explanation": "",

        "example_validation": {},

        "example_generated": False,

        "example_source": "",

        "status": "active" if index == 0 else "pending",

        "attempts": 0,

        # Consecutive genuinely-wrong values in a row, not counting
        # off-track chatter — reset to 0 by any passed/warning/skip.
        # Drives the escalate-to-expert offer once it hits
        # MAX_FAILED_ATTEMPTS.
        "failed_streak": 0,

        "last_verdict": None,

        "conversation": [],
    }


def build_steps(rules: list[dict] | None) -> list[dict]:
    """Turn a rule list into the ordered steps of a walkthrough."""

    if not rules:
        return []

    return [
        build_step(rule, index)
        for index, rule in enumerate(rules)
        if rule is not None
    ]


def find_rule(rules: list[dict] | None, rule_id) -> Optional[dict]:
    """Locate the original rule backing a step."""

    if not rules:
        return None

    for rule in rules:
        if isinstance(rule, dict) and str(rule.get("id")) == str(rule_id):
            return rule

    return None


# ============================================================
# EXAMPLE PREPARATION
# ============================================================

def _generate_ai_example(rule: dict) -> dict:
    """
    Ask the model for an example, then let the validator decide.

    The model never rules on its own output. The explanation Groq
    returns alongside the example is carried through too — it
    describes the general format the field expects, not just why
    this one value happens to pass, so the caller can show the user
    more than a bare value to copy.
    """

    if not isinstance(rule, dict):
        return {"example": "", "valid": False}

    try:
        result = generate_rule_example_with_retry(
            rule=rule,
            max_retries=MAX_RETRIES,
        )
    except Exception:
        logger.exception(
            "Example generation failed for rule '%s'",
            rule.get("name", "unknown"),
        )
        return {"example": "", "valid": False}

    if not isinstance(result, dict):
        return {"example": "", "valid": False}

    example = str(result.get("example") or "").strip()
    explanation = str(result.get("explanation") or "").strip()

    if not example:
        return {"example": "", "valid": False, "explanation": explanation}

    try:
        validation = deterministic_validate_example(
            example=example,
            rule=rule,
        )
    except Exception:
        logger.exception(
            "Example validation failed for rule '%s'",
            rule.get("name", "unknown"),
        )
        return {"example": "", "valid": False}

    if not validation.get("valid"):
        return {"example": "", "valid": False, "validation": validation}

    return {
        "example": example,
        "valid": True,
        "validation": validation,
        "explanation": explanation,
    }


def prepare_example(
    step: dict,
    rule: Optional[dict] = None,
    force_new: bool = False,
) -> str:
    """
    Get the example for THIS step.

    Order:

        1. an example already prepared for this step
        2. the example computed for its rule at task-creation time
        3. a fresh AI example, validated before use
        4. the deterministic builder
        5. the step's name

    Steps 2 and 4 are already verified against the rule by
    example_utils, so what is returned is an example that would pass
    if the user typed it.
    """

    existing = str(step.get("suggested_example") or "").strip()

    if existing and not force_new:
        return existing

    # Precomputed at task creation and validated there. Since
    # build_rules_with_examples() now asks Groq for this value, its
    # true origin travels with the rule ("ai" normally, "rule" only
    # for a literal example lifted straight from the document text,
    # "ai_unavailable" if Groq could not produce one at upload time).

    explicit = str(
        step.get("example_input")
        or step.get("example")
        or ""
    ).strip()

    if explicit:
        step["suggested_example"] = explicit
        step["example_generated"] = False
        step["example_source"] = (
            (rule or {}).get("example_source") or "rule"
        )
        step["example_explanation"] = str(
            (rule or {}).get("example_explanation") or ""
        ).strip()
        return explicit

    if rule:
        generated = _generate_ai_example(rule)
        value = str(generated.get("example") or "").strip()

        if value and generated.get("valid"):
            step["suggested_example"] = value
            step["example_validation"] = generated.get("validation", {})
            step["example_generated"] = True
            step["example_source"] = "ai"
            step["example_explanation"] = str(
                generated.get("explanation") or ""
            ).strip()
            return value

        # A rule was available but Groq could not produce a validated
        # example for it. No silent local substitute here: the caller
        # is told plainly that AI is unavailable rather than being
        # shown a value the model never actually produced.
        step["suggested_example"] = ""
        step["example_generated"] = False
        step["example_source"] = "ai_unavailable"
        step["example_explanation"] = ""
        return ""

    # No rule to ask AI about at all (e.g. an orphaned step whose
    # original rule could not be found) — the deterministic builder is
    # the only source of an example here, not a substitute for AI.

    try:
        value = str(build_example_value(step) or "").strip()
    except Exception:
        logger.exception(
            "Deterministic example builder failed for step '%s'",
            step.get("rule_name", "unknown"),
        )
        value = ""

    if value:
        step["suggested_example"] = value
        step["example_generated"] = False
        step["example_source"] = "builder"
        step["example_explanation"] = ""
        return value

    fallback = presenter.step_label(step)

    step["suggested_example"] = ""
    step["example_source"] = "none"
    step["example_explanation"] = ""

    return f"A valid {fallback}" if fallback != "This step" else ""


# ============================================================
# COLLECTION STATE (composite steps)
# ============================================================

def ensure_collection_started(step: dict) -> dict:
    """
    Begin per-field collection for a composite step, or return the
    progress already in place.

    Idempotent, so every caller that might be the first to show a
    composite step — take_turn's advance branch, a guided session's
    first step, a workflow's first step — can call it unconditionally
    without worrying about stepping on collection already under way.

    Operates on the step's own copies of input_shape/columns/item_rule
    (build_step already mirrors these from the rule), so no rule
    lookup is required here.
    """

    shape = composite_rules.input_shape(step)

    if shape not in composite_rules.COMPOSITE_SHAPES:
        step.pop("composite_progress", None)
        return {}

    existing = step.get("composite_progress")

    if isinstance(existing, dict) and existing.get("active"):
        return existing

    progress = {
        "active": True,
        "shape": shape,
        "stage": "collecting",
        "column_index": 0,
        "row_index": 0,
        "rows": [],
        "current_row": [],
        "items": [],
    }

    step["composite_progress"] = progress

    return progress


def _explain_for(rule: dict, value: str, conversation: list) -> str:
    """
    Ask the model to explain a rule in plain language, tolerating a
    Groq outage the same way every other explanation call site does.

    Shared by every parked state that can be interrupted with an
    explanation request — a step waiting on a yes/no, an advance
    confirmation, or one field of a table/list.
    """

    try:
        return run_rule_followup(
            rule=rule,
            user_message=value,
            conversation_history=conversation,
        )
    except GroqNetworkError:
        logger.warning(
            "Groq unreachable while explaining '%s'",
            (rule or {}).get("name") or (rule or {}).get("rule_name") or "unknown",
        )
    except Exception:
        logger.exception(
            "Explanation failed for '%s'",
            (rule or {}).get("name") or (rule or {}).get("rule_name") or "unknown",
        )

    return ""


# ============================================================
# ONE TURN OF THE WALKTHROUGH
# ============================================================

def _asks_rather_than_answers(
    value: str,
    step: dict,
    rule: dict,
) -> bool:
    """
    Whether an otherwise-passing value is really a question.

    Applied only to free-text steps. Those validate on word count
    alone, so anything long enough passes — including a request for
    help. Steps with a real format are left alone: a value that
    satisfies "TRF followed by 3 digits" is an answer whatever it
    reads like, and second-guessing it would reject correct input.

    Constraints come from the rule, which carries `name`; the step
    carries `rule_name` and is used only for its label.
    """

    if composite_rules.input_shape(rule) in composite_rules.COMPOSITE_SHAPES:
        return False

    try:
        from app.services.groq_service import _get_effective_constraints

        constraints = _get_effective_constraints(rule)
    except Exception:
        return False

    if constraints.get("content_type") != "narrative":
        return False

    intent = input_intent.classify(value, step)

    return intent in (
        input_intent.QUESTION_STEP,
        input_intent.QUESTION_OTHER,
        input_intent.CHITCHAT,
    )


def _advance_to_next_step(
    *,
    steps: list[dict],
    current_index: int,
    rules: list[dict],
    step: dict,
    value: str,
    verdict: dict,
    skipped: bool = False,
) -> dict:
    """
    Complete the current step and open the next one immediately, in
    the same reply — confirmation and the next step's prompt travel
    together with no separate "ready?" turn in between.

    Shared by a PASSED turn, a WARNING accepted via
    _take_warning_acceptance_turn, and a step skipped via
    _wants_to_skip_step — all three end the step the same way, just
    with different confirmation wording and verdict attached.
    """

    total = len(steps)

    step["status"] = "completed"
    step["user_value"] = value
    step["off_track_count"] = 0

    if skipped:
        step["skipped"] = True

    # The user just recovered from an error. Remember how, so the
    # next person who hits the same kind of error can be told.
    # Only values that have passed validation reach here. A skipped
    # step was never fixed, so there is nothing to record.

    rejected = str(step.get("last_rejected") or "").strip()

    if rejected and not skipped:
        try:
            correction_memory.record_correction(
                step=step,
                rejected=rejected,
                accepted=value,
                verdict=step.get("last_failed_verdict") or {},
            )
        except Exception:
            logger.exception(
                "Could not record a correction for step '%s'",
                step.get("rule_name", "unknown"),
            )

    if rejected:
        step.pop("last_rejected", None)
        step.pop("last_failed_verdict", None)

    confirmation = (
        presenter.build_skip_message(step, current_index, total)
        if skipped
        else presenter.build_success_message(
            step,
            current_index,
            total,
            next_step=None,
            submitted_value=value,
        )
    )

    next_index = current_index + 1

    if next_index < total:

        next_step = steps[next_index]
        next_step["status"] = "active"

        next_rule = find_rule(rules, next_step.get("rule_id"))

        prepare_example(
            next_step,
            next_rule,
            force_new=True,
        )

        ensure_collection_started(next_step)

        blocks = (
            confirmation
            + presenter.build_moving_on_message(next_step, next_index, total)
            + presenter.build_step_prompt(next_step, next_index, total)
        )

        return {
            "passed": True,
            "current_index": next_index,
            "all_completed": False,
            "message_blocks": blocks,
            "message_lines": presenter.lines_of(blocks),
            "step": step,
            "next_step": next_step,
            "verdict": verdict,
            "public_verdict": presenter.public_verdict(verdict),
        }

    final_blocks = confirmation + presenter.build_all_completed_message(total)

    return {
        "passed": True,
        "current_index": next_index,
        "all_completed": True,
        "message_blocks": final_blocks,
        "message_lines": presenter.lines_of(final_blocks),
        "step": step,
        "next_step": None,
        "verdict": verdict,
        "public_verdict": presenter.public_verdict(verdict),
    }


# ============================================================
# WARNING ACCEPT / DECLINE
# ============================================================

_YES_WORDS = {
    "yes", "y", "yeah", "yep", "yup", "accept", "confirm", "continue",
    "proceed", "ok", "okay", "alright", "fine", "sure",
}
_NO_WORDS = {"no", "n", "nope", "decline", "cancel", "different", "change", "reject"}

# Natural sentences that mean the same as a bare yes/no, so the user
# is not forced to answer in a single keyword — e.g. "I'll continue
# with this file" or "let's just go with it" both mean yes.
_YES_PATTERNS = (
    r"\b(i'?ll|i\s+will|let'?s|lets)\s+"
    r"(continue|keep|stick|proceed|go)\b",
    r"\bkeep(ing)?\s+(this|it|the\s+same)\b",
    r"\bgo\s+(ahead|with\s+(this|it))\b",
    r"\bthat'?s\s+fine\b",
    r"\b(i'?m|im)\s+(ok|okay|fine|good)\s+with\s+(this|it)\b",
)
_NO_PATTERNS = (
    r"\b(let\s+me|i'?ll|i'd|i\s+want\s+to)\s+"
    r"(try|use|pick)\s+(something|a\s+different|another)\b",
    r"\bi'?d\s+rather\s+(not|change|use\s+something\s+else)\b",
    r"\bnot\s+this\s+one\b",
    r"\bsomething\s+else\b",
    r"\b(different|another)\s+(one|value|file)\b",
)


def _classify_yes_no(value: str) -> str:
    """
    Whether a reply to a WARNING's accept/decline prompt means yes or
    no.

    Not limited to a fixed word list — a full sentence in the user's
    own words ("I'll continue with this file") is read the same way
    as a bare "yes".
    """

    lowered = value.strip().lower()

    if not lowered:
        return "unclear"

    if lowered in _YES_WORDS or any(
        re.search(pattern, lowered) for pattern in _YES_PATTERNS
    ):
        return "yes"

    if lowered in _NO_WORDS or any(
        re.search(pattern, lowered) for pattern in _NO_PATTERNS
    ):
        return "no"

    return "unclear"


def _take_warning_acceptance_turn(
    *,
    steps: list[dict],
    current_index: int,
    rules: list[dict],
    user_input: str,
    step: dict,
    rule: dict,
    awaiting: dict,
) -> dict:
    """One turn while a step is parked awaiting accept/decline of a WARNING."""

    total = len(steps)
    value = str(user_input or "").strip()

    # Asking to skip outright, rather than accepting or declining the
    # flagged value, still has to work while a WARNING is parked here —
    # otherwise an optional step whose risky value was declined-in-spirit
    # ("no error", then "skip this") loops on the same accept/decline
    # prompt forever, since neither reads as a plain yes or no.
    if _wants_to_skip_step(value) and _step_is_optional(rule):

        step.pop("awaiting_risk_acceptance", None)

        return _advance_to_next_step(
            steps=steps,
            current_index=current_index,
            rules=rules,
            step=step,
            value="",
            verdict={"status": "skipped", "passed": True},
            skipped=True,
        )

    decision = _classify_yes_no(value)

    if decision == "yes":

        step.pop("awaiting_risk_acceptance", None)
        step["warning_accepted"] = True

        accepted_value = str(awaiting.get("value") or "")
        verdict = awaiting.get("verdict") or {
            "status": "warning",
            "passed": True,
        }

        return _advance_to_next_step(
            steps=steps,
            current_index=current_index,
            rules=rules,
            step=step,
            value=accepted_value,
            verdict=verdict,
        )

    if decision == "no":

        step.pop("awaiting_risk_acceptance", None)
        step["status"] = "active"

        correction = prepare_example(step, rule, force_new=False)

        blocks = presenter.build_warning_declined_message(
            step,
            current_index,
            total,
            example=correction,
        )

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": True,
            "intent": "warning_declined",
            "message_blocks": blocks,
            "message_lines": presenter.lines_of(blocks),
            "step": step,
            "next_step": None,
            "verdict": {"status": "failed", "passed": False},
            "public_verdict": {"status": "failed", "passed": False},
        }

    # Unclear reply: might be a question about why this was flagged
    # rather than an unrecognized yes/no. Answered in place, then the
    # same accept/decline prompt is shown again unchanged.

    verdict = awaiting.get("verdict") or {}

    explanation_blocks: list[dict] = []

    if input_intent.is_question(value):
        explanation = _explain_for(rule, value, step.get("conversation", []))

        if explanation:
            explanation_blocks = presenter.build_step_explanation_message(
                explanation,
            )

    blocks = explanation_blocks + presenter.build_warning_message(
        step,
        current_index,
        total,
        verdict.get("warning_reason", ""),
        example=str(awaiting.get("value") or ""),
    )

    return {
        "passed": False,
        "current_index": current_index,
        "all_completed": False,
        "handled": True,
        "intent": "warning",
        "message_blocks": blocks,
        "message_lines": presenter.lines_of(blocks),
        "step": step,
        "next_step": None,
        "verdict": {"status": "warning", "passed": True},
        "public_verdict": {"status": "warning", "passed": True},
    }


# ============================================================
# ESCALATE-TO-EXPERT CHOICE
# ============================================================

_ESCALATE_WORDS = {"1", "escalate", "expert", "escalate to expert", "help"}
_RETRY_WORDS = {"2", "try again", "retry", "try", "again"}


def _classify_escalation_choice(value: str) -> str:
    """Whether a reply to the escalation menu picked [1] or [2]."""

    lowered = value.strip().lower().rstrip(".")

    if lowered in _ESCALATE_WORDS:
        return "escalate"

    if lowered in _RETRY_WORDS:
        return "retry"

    return "unclear"


def _take_escalation_choice_turn(
    *,
    steps: list[dict],
    current_index: int,
    rules: list[dict],
    user_input: str,
    step: dict,
    escalation: dict,
) -> dict:
    """One turn while a step is parked awaiting an escalation choice."""

    total = len(steps)
    value = str(user_input or "").strip()
    choice = _classify_escalation_choice(value)

    if choice == "escalate":

        attempts = int(step.get("failed_streak", 0))
        verdict = escalation.get("verdict") or {}

        step.pop("awaiting_escalation_choice", None)
        step["failed_streak"] = 0
        step["escalated"] = True

        blocks = presenter.build_escalation_summary_message(
            step, current_index, total, attempts, verdict,
        )

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": True,
            "intent": "escalated",
            "message_blocks": blocks,
            "message_lines": presenter.lines_of(blocks),
            "step": step,
            "next_step": None,
            "verdict": verdict,
            "public_verdict": presenter.public_verdict(verdict),
        }

    if choice == "retry":

        step.pop("awaiting_escalation_choice", None)
        step["failed_streak"] = 0

        blocks = presenter.build_escalation_retry_message(
            step, current_index, total,
        )

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": True,
            "intent": "escalation_retry",
            "message_blocks": blocks,
            "message_lines": presenter.lines_of(blocks),
            "step": step,
            "next_step": None,
            "verdict": {"status": "failed", "passed": False},
            "public_verdict": {"status": "failed", "passed": False},
        }

    # Unclear reply — repeat the same menu unchanged.

    blocks = presenter.build_escalation_unclear_message(
        step, current_index, total,
    )

    return {
        "passed": False,
        "current_index": current_index,
        "all_completed": False,
        "handled": True,
        "intent": "escalation_offered",
        "message_blocks": blocks,
        "message_lines": presenter.lines_of(blocks),
        "step": step,
        "next_step": None,
        "verdict": {"status": "failed", "passed": False},
        "public_verdict": {"status": "failed", "passed": False},
    }


_SKIP_ATTACHMENT_WORDS = {"skip", "no", "never mind", "nevermind", "cancel"}


def _take_awaiting_attachment_turn(
    *,
    steps: list[dict],
    current_index: int,
    rules: list[dict],
    step: dict,
    user_input: str,
) -> dict:
    """
    One turn while a step is parked waiting for the file/screenshot
    the AI asked for. A plain-text reply here is never judged as a
    value — only "skip" resumes ordinary validation, a question is
    answered without resuming it, and anything else just repeats the
    reminder. The actual attachment arrives through resolve_attachment(),
    a separate entry point the router calls once the upload has been
    read.
    """

    total = len(steps)
    raw_value = str(user_input or "").strip()
    value = raw_value.lower()

    if value in _SKIP_ATTACHMENT_WORDS:
        step.pop("awaiting_attachment", None)
        step["off_track_count"] = 0

        blocks = presenter.build_step_prompt(step, current_index, total)

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": True,
            "intent": "attachment_skipped",
            "message_blocks": blocks,
            "message_lines": presenter.lines_of(blocks),
            "step": step,
            "next_step": None,
            "verdict": {"status": "failed", "passed": False},
            "public_verdict": {"status": "failed", "passed": False},
        }

    explanation_blocks: list[dict] = []

    if input_intent.is_question(raw_value):
        rule = find_rule(rules, step.get("rule_id")) or step
        explanation = _explain_for(rule, raw_value, step.get("conversation", []))

        if explanation:
            explanation_blocks = presenter.build_step_explanation_message(
                explanation,
            )

    blocks = explanation_blocks + presenter.build_awaiting_attachment_reminder_message(
        step, current_index, total,
    )

    return {
        "passed": False,
        "current_index": current_index,
        "all_completed": False,
        "handled": True,
        "intent": "awaiting_attachment",
        "message_blocks": blocks,
        "message_lines": presenter.lines_of(blocks),
        "step": step,
        "next_step": None,
        "verdict": {"status": "failed", "passed": False},
        "public_verdict": {"status": "failed", "passed": False},
    }


def resolve_attachment(
    *,
    steps: list[dict],
    current_index: int,
    rules: list[dict],
    step: dict,
    attachment_summary: str,
) -> dict:
    """
    Process the file/screenshot the AI asked for, and reply with an
    explanation informed by it. The step stays active either way — an
    attachment answers a question, it is never itself the step's value.

    attachment_summary is plain text: extracted document content, or a
    short note naming an image when it has no extractable text (no
    OCR/vision pipeline reads pixels here — see StepAttachment).
    """

    total = len(steps)

    rule = find_rule(rules, step.get("rule_id")) or step

    step.pop("awaiting_attachment", None)
    step["off_track_count"] = 0

    explanation = ""

    try:
        explanation = run_rule_followup(
            rule=rule,
            user_message=(
                "I attached a file to help explain what I mean:\n\n"
                f"{attachment_summary}\n\n"
                "Based on this, please explain what you need from me for this step."
            ),
            conversation_history=step.get("conversation", []),
            previous_verdict=step.get("last_verdict"),
        )
    except GroqNetworkError:
        logger.warning(
            "Groq unreachable while explaining an attachment for step '%s'",
            step.get("rule_name", "unknown"),
        )
    except Exception:
        logger.exception(
            "Attachment explanation failed for step '%s'",
            step.get("rule_name", "unknown"),
        )

    example = prepare_example(step, rule, force_new=False)

    blocks = presenter.build_attachment_processed_message(
        step, current_index, total, explanation, example=example,
    )

    return {
        "passed": False,
        "current_index": current_index,
        "all_completed": False,
        "handled": True,
        "intent": "attachment_processed",
        "message_blocks": blocks,
        "message_lines": presenter.lines_of(blocks),
        "step": step,
        "next_step": None,
        "verdict": {"status": "failed", "passed": False},
        "public_verdict": {"status": "failed", "passed": False},
    }


_SKIP_STEP_WORDS = {"skip", "n/a", "na", "not applicable"}

# Phrases that ask to move past the current step outright, rather
# than answering it — e.g. "skip this", "go to the next step". Kept
# narrow and explicit on purpose: a bare "no" or "next" is left alone
# here since either could be a real answer to some step.
_SKIP_STEP_PATTERNS = (
    r"\bskip\s+(this|it|that)\b",
    r"\b(go|move|jump)\s+(on\s+)?to\s+the\s+next\s+step\b",
    r"\bnext\s+step\s*,?\s*please\b",
    r"\bcan\s+(i|we)\s+skip\b",
    r"\bi'?ll\s+skip\s+(this|it)\b",
    r"\bi\s+don'?t\s+have\s+(this|that|it)\b",
    r"\bleave\s+(this|it)\s+(blank|empty|out)\b",
)


def _wants_to_skip_step(value: str) -> bool:
    """Whether the user is asking to move past this step, not answer it."""

    lowered = value.strip().lower()

    if not lowered:
        return False

    if lowered in _SKIP_STEP_WORDS:
        return True

    return any(re.search(pattern, lowered) for pattern in _SKIP_STEP_PATTERNS)


def _step_is_optional(rule: dict) -> bool:
    """Whether this step's own rule allows moving on with no answer at all."""

    try:
        from app.services.groq_service import _get_effective_constraints

        constraints = _get_effective_constraints(rule)
    except Exception:
        return False

    return constraints.get("required", True) is False


def take_turn(
    *,
    steps: list[dict],
    current_index: int,
    rules: list[dict],
    user_input: str,
) -> dict:
    """
    Judge one submission and decide what happens next.

    Mutates `steps` in place — attempt counts, status, conversation and
    the example prepared for whichever step becomes active — and hands
    back what the caller should persist and show.

    Returns:

        passed          the submission satisfied the current step
        current_index   the step the user is on AFTER this turn
        all_completed   the walkthrough finished on this turn
        message_blocks  user-facing lines tagged with what each is
                        (heading / instruction / example / problem /
                        confirmation), already rule-free
        message_lines   the same lines as plain text
        step            the step that was judged
        next_step       the step now active, if the user advanced
        verdict         full internal verdict (never sent to a client)
        public_verdict  the sanitized verdict that may be sent
    """

    total = len(steps)

    if not steps or not (0 <= current_index < total):
        raise ValueError("The walkthrough has no step at that position.")

    step = steps[current_index]

    rule = find_rule(rules, step.get("rule_id"))

    if rule is None:
        # Fall back to the step's own copy of the rule fields so a
        # missing original cannot strand the user.
        rule = step

    # A table/list step being filled in one field at a time never
    # reaches the whole-answer judgment below until collection is
    # done — each submission here is one cell or item.
    progress = step.get("composite_progress")

    if isinstance(progress, dict) and progress.get("active"):
        return _take_collection_turn(
            steps=steps,
            current_index=current_index,
            rules=rules,
            user_input=user_input,
            step=step,
            rule=rule,
        )

    # A value that triggered a WARNING is parked here awaiting an
    # explicit accept/decline, rather than being judged again as a
    # fresh value against the rule.
    awaiting = step.get("awaiting_risk_acceptance")

    if isinstance(awaiting, dict):
        return _take_warning_acceptance_turn(
            steps=steps,
            current_index=current_index,
            rules=rules,
            user_input=user_input,
            step=step,
            rule=rule,
            awaiting=awaiting,
        )

    # Repeated failures on this step already offered escalation —
    # parked here awaiting the user's [1]/[2] choice, rather than
    # being judged again as a fresh value against the rule.
    escalation = step.get("awaiting_escalation_choice")

    if isinstance(escalation, dict):
        return _take_escalation_choice_turn(
            steps=steps,
            current_index=current_index,
            rules=rules,
            user_input=user_input,
            step=step,
            escalation=escalation,
        )

    # A step parked waiting for the file/screenshot the AI asked for
    # (see _asks_for_attachment below) never reaches ordinary judgment
    # for a plain-text turn — only a real attachment (handled by
    # resolve_attachment, called from outside take_turn) or the word
    # "skip" moves it forward.
    if step.get("awaiting_attachment"):
        return _take_awaiting_attachment_turn(
            steps=steps,
            current_index=current_index,
            rules=rules,
            step=step,
            user_input=user_input,
        )

    value = str(user_input or "").strip()

    # The user is asking to move past this step rather than answer
    # it. Only honoured when the step's own rule does not require a
    # value — an obligatory step is explained and re-shown instead.
    if _wants_to_skip_step(value):

        if _step_is_optional(rule):
            return _advance_to_next_step(
                steps=steps,
                current_index=current_index,
                rules=rules,
                step=step,
                value="",
                verdict={"status": "skipped", "passed": True},
                skipped=True,
            )

        cannot_skip_blocks = presenter.build_cannot_skip_message(
            step, current_index, total,
        )

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": True,
            "intent": "skip_declined",
            "message_blocks": cannot_skip_blocks,
            "message_lines": presenter.lines_of(cannot_skip_blocks),
            "step": step,
            "next_step": None,
            "verdict": {"status": "failed", "passed": False},
            "public_verdict": {"status": "failed", "passed": False},
        }

    known_example = str(step.get("suggested_example") or "").strip()

    # --------------------------------------------------------
    # Judge. The step's own example is passed through so this
    # costs no model call.
    # --------------------------------------------------------

    try:

        verdict = run_rule_workflow(
            rule=rule,
            user_input=value,
            conversation_history=step.get("conversation", []),
            known_example=known_example,
        )

    except GroqNetworkError:

        logger.warning(
            "Groq unreachable while validating step '%s'",
            step.get("rule_name", "unknown"),
        )

        network_blocks = presenter.build_network_error_message(
            step,
            current_index,
            total,
            example=known_example,
        )

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": False,
            "intent": "network_error",
            "message_blocks": network_blocks,
            "message_lines": presenter.lines_of(network_blocks),
            "step": step,
            "next_step": None,
            "verdict": {"status": "network_error", "passed": False},
            "public_verdict": {"status": "network_error", "passed": False},
        }

    except Exception:

        # The check itself failed. Nothing is wrong with what the
        # user typed, so they are told that rather than being asked
        # to correct a value that may well be right.

        logger.exception(
            "Validation failed for step '%s'",
            step.get("rule_name", "unknown"),
        )

        error_blocks = presenter.build_error_message(
            step,
            current_index,
            total,
            example=known_example,
        )

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": False,
            "intent": "error",
            "message_blocks": error_blocks,
            "message_lines": presenter.lines_of(error_blocks),
            "step": step,
            "next_step": None,
            "verdict": {"status": "error", "passed": False},
            "public_verdict": {"status": "error", "passed": False},
        }

    if not isinstance(verdict, dict):
        verdict = {
            "status": "failed",
            "passed": False,
            "validation_errors": [],
        }

    status = verdict.get("status")

    # PASSED, WARNING and NEEDS_MORE_INFO all mean the value cleared
    # hard validation — only FAILED means it did not.
    content_passed = status in ("passed", "warning", "needs_more_info")

    # A prose step only checks that enough words were written, so a
    # question long enough to clear the count was being ACCEPTED as
    # the content: "give me an example need help" satisfied a
    # three-word minimum. A question is never the answer to a step,
    # however long it is. Checked against any of the three positive
    # outcomes, not just PASSED, so a question that happens to also
    # be missing a narrative topic is still caught here rather than
    # answered with "please also address X".

    if content_passed and _asks_rather_than_answers(value, step, rule):
        content_passed = False
        status = "failed"
        verdict = {
            "status": "failed",
            "passed": False,
            "validation_errors": [],
        }

    passed = status == "passed"

    step["last_verdict"] = verdict

    # An attempt is a try at the value. A question or a greeting is
    # counted below only if it was really an attempt. NEEDS_MORE_INFO
    # is not counted — the spec treats it as "resume the same step",
    # not a strike against the user.
    if status in ("passed", "warning"):
        step["attempts"] = int(step.get("attempts", 0)) + 1
        step["failed_streak"] = 0

    # --------------------------------------------------------
    # Passed: complete this step, open the next
    # --------------------------------------------------------

    if passed:
        return _advance_to_next_step(
            steps=steps,
            current_index=current_index,
            rules=rules,
            step=step,
            value=value,
            verdict=verdict,
        )

    # --------------------------------------------------------
    # Warning: hard-valid but risky. Park the value and ask the
    # user to explicitly accept or decline before advancing.
    # --------------------------------------------------------

    if status == "warning":

        step["status"] = "active"
        step["awaiting_risk_acceptance"] = {
            "value": value,
            "verdict": verdict,
        }

        blocks = presenter.build_warning_message(
            step,
            current_index,
            total,
            verdict.get("warning_reason", ""),
            example=value,
        )

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": True,
            "intent": "warning",
            "message_blocks": blocks,
            "message_lines": presenter.lines_of(blocks),
            "step": step,
            "next_step": None,
            "verdict": verdict,
            "public_verdict": presenter.public_verdict(verdict),
        }

    # --------------------------------------------------------
    # Needs more info: hard-valid but incomplete. Stay on the SAME
    # step and name exactly what is still missing.
    # --------------------------------------------------------

    if status == "needs_more_info":

        step["status"] = "active"

        blocks = presenter.build_need_more_info_message(
            step,
            current_index,
            total,
            verdict.get("missing_topics", []),
        )

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": True,
            "intent": "needs_more_info",
            "message_blocks": blocks,
            "message_lines": presenter.lines_of(blocks),
            "step": step,
            "next_step": None,
            "verdict": verdict,
            "public_verdict": presenter.public_verdict(verdict),
        }

    # --------------------------------------------------------
    # Failed: work out what the user was doing, then reply
    #
    # Classification runs only here, on input that already failed,
    # so a correct answer can never be mistaken for a question.
    # --------------------------------------------------------

    step["status"] = "active"

    correction = str(verdict.get("suggested_fix") or "").strip()

    if correction:
        step["suggested_example"] = correction
    else:
        correction = prepare_example(step, rule, force_new=False)

    intent = input_intent.classify(value, step)

    # An unintelligible-looking value still gets the corrective
    # message whenever the validator had something specific to say.
    # "bh" on a rate step is a wrong number, and "must be a valid
    # number" helps far more than "I did not understand" — which is
    # what the user saw. Conversational input is overridden either
    # way, since no correction applies to a question or a greeting.

    if (
        intent == input_intent.UNINTELLIGIBLE
        and not input_intent.is_pure_symbols(value)
        and presenter.has_specific_problem(verdict)
    ):
        intent = input_intent.VALUE

    if intent != input_intent.VALUE:

        # Not an attempt at the value: answer what they actually did
        # and repeat what the step needs. No attempt is recorded.

        step["off_track_count"] = int(step.get("off_track_count", 0)) + 1

        # Words alone have not gotten through after several tries at
        # explaining the same step — ask to see what the user is
        # actually working with instead of explaining a third time.
        if (
            intent == input_intent.QUESTION_STEP
            and step["off_track_count"] >= CONFUSION_THRESHOLD
        ):
            step["awaiting_attachment"] = True
            step["off_track_count"] = 0

            attachment_request = presenter.build_request_attachment_message(
                step, current_index, total,
            )

            return {
                "passed": False,
                "current_index": current_index,
                "all_completed": False,
                "handled": True,
                "intent": "attachment_requested",
                "message_blocks": attachment_request,
                "message_lines": presenter.lines_of(attachment_request),
                "step": step,
                "next_step": None,
                "verdict": verdict,
                "public_verdict": {
                    "status": "not_a_value",
                    "passed": False,
                },
            }

        # A genuine question about this step gets a fresh, plain-
        # language answer from the model — scoped to this one rule
        # (run_rule_followup), not just the same canned reminder.
        ai_explanation = ""

        if intent == input_intent.QUESTION_STEP:
            try:
                ai_explanation = run_rule_followup(
                    rule=rule,
                    user_message=value,
                    conversation_history=step.get("conversation", []),
                    previous_verdict=step.get("last_verdict"),
                )
            except GroqNetworkError:
                logger.warning(
                    "Groq unreachable while explaining step '%s'",
                    step.get("rule_name", "unknown"),
                )
            except Exception:
                logger.exception(
                    "Step explanation failed for step '%s'",
                    step.get("rule_name", "unknown"),
                )

        # A greeting or small talk mid-walkthrough gets a real, warm
        # reply instead of the same static line every time — falls back
        # to step_presenter's canned line if Groq is unreachable.
        elif intent == input_intent.CHITCHAT:
            try:
                ai_explanation = get_chitchat_reply(
                    user_message=value,
                    step_label=step.get("rule_name") or step.get("name") or "",
                )
            except GroqNetworkError:
                logger.warning(
                    "Groq unreachable while replying to chitchat on step '%s'",
                    step.get("rule_name", "unknown"),
                )
            except Exception:
                logger.exception(
                    "Chitchat reply failed for step '%s'",
                    step.get("rule_name", "unknown"),
                )

        off_track = presenter.build_off_track_message(
            step,
            current_index,
            total,
            intent,
            example=correction,
            ai_explanation=ai_explanation,
        )

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": False,
            "intent": intent,
            "message_blocks": off_track,
            "message_lines": presenter.lines_of(off_track),
            "step": step,
            "next_step": None,
            "verdict": verdict,
            "public_verdict": {
                "status": "not_a_value",
                "passed": False,
            },
        }

    step["off_track_count"] = 0
    step["attempts"] = int(step.get("attempts", 0)) + 1
    step["failed_streak"] = int(step.get("failed_streak", 0)) + 1

    # Held so that, if the next value succeeds, the pair can be
    # learned as a way past this error.
    step["last_rejected"] = value
    step["last_failed_verdict"] = {
        "validation_errors": verdict.get("validation_errors", []),
    }

    # The same step has failed too many times in a row — stop
    # repeating "how to fix" and offer to escalate instead.
    if step["failed_streak"] >= MAX_FAILED_ATTEMPTS:

        step["awaiting_escalation_choice"] = {"verdict": verdict}

        escalation_blocks = presenter.build_escalation_offer_message(
            step, current_index, total, step["failed_streak"],
        )

        return {
            "passed": False,
            "current_index": current_index,
            "all_completed": False,
            "handled": True,
            "intent": "escalation_offered",
            "message_blocks": escalation_blocks,
            "message_lines": presenter.lines_of(escalation_blocks),
            "step": step,
            "next_step": None,
            "verdict": verdict,
            "public_verdict": presenter.public_verdict(verdict),
        }

    try:
        # The rule is passed so a remembered value is only offered
        # when it would pass THIS rule.
        learned = correction_memory.guidance_for(verdict, step, rule)
    except Exception:
        logger.exception("Could not read correction memory")
        learned = ""

    return {
        "passed": False,
        "current_index": current_index,
        "all_completed": False,
        "handled": True,
        "intent": intent,
        "message_blocks": presenter.build_failure_message(
            step,
            current_index,
            total,
            verdict,
            corrected_example=correction,
            learned_hint=learned,
            submitted_value=value,
        ),
        "message_lines": presenter.lines_of(
            presenter.build_failure_message(
                step,
                current_index,
                total,
                verdict,
                corrected_example=correction,
                learned_hint=learned,
                submitted_value=value,
            )
        ),
        "step": step,
        "next_step": None,
        "verdict": verdict,
        "public_verdict": presenter.public_verdict(verdict),
    }


# ============================================================
# ONE TURN OF FIELD-BY-FIELD COLLECTION
#
# A table/list step is filled one cell or item at a time rather than
# as a single pasted blob. Every turn here either stays on the same
# step (one more field collected, or a problem with the one just
# submitted) or, once the user is done, hands the assembled answer to
# take_turn() exactly as if it had arrived in one message — so pass/
# fail, advancing, correction-memory and message wording for the
# FINAL judgment are never duplicated here.
# ============================================================

_ROW_ADD_WORDS = {"add", "another", "add row", "add another", "more", "yes", "y", "next row"}
_ROW_DONE_WORDS = {"done", "finish", "finished", "no", "n", "that's all", "thats all", "stop", "complete", "no more"}


def _classify_row_decision(value: str) -> str:
    """Whether a reply to "add another row or finish?" means add or stop."""

    lowered = value.strip().lower()

    if lowered in _ROW_ADD_WORDS:
        return "add"

    if lowered in _ROW_DONE_WORDS:
        return "done"

    return "unclear"


def _is_done_keyword(value: str) -> bool:
    return value.strip().lower() in _ROW_DONE_WORDS


def _collection_stay_put(step: dict, current_index: int, blocks: list) -> dict:
    """The shared shape of a turn that stays on the current field."""

    return {
        "passed": False,
        "current_index": current_index,
        "all_completed": False,
        "handled": True,
        "intent": "collecting",
        "message_blocks": blocks,
        "message_lines": presenter.lines_of(blocks),
        "step": step,
        "next_step": None,
        "verdict": {"status": "collecting", "passed": False},
        "public_verdict": {"status": "collecting", "passed": False},
    }


def _take_table_collection_turn(
    *, steps: list[dict], current_index: int, rules: list[dict],
    user_input: str, step: dict, rule: dict,
) -> dict:

    progress = step["composite_progress"]
    value = str(user_input or "").strip()
    total = len(steps)

    if progress["stage"] == "row_decision":

        decision = _classify_row_decision(value)

        if decision == "add":
            progress["stage"] = "collecting"
            progress["row_index"] += 1
            progress["column_index"] = 0
            progress["current_row"] = []

            return _collection_stay_put(
                step, current_index,
                presenter.build_collection_prompt(step, current_index, total),
            )

        if decision == "done":

            minimum = composite_rules.minimum_rows(step)

            if len(progress["rows"]) < minimum:
                return _collection_stay_put(
                    step, current_index,
                    presenter.build_collection_shortfall_message(
                        step, current_index, total,
                        kind="rows", minimum=minimum, have=len(progress["rows"]),
                    ),
                )

            return _finalize_collection(
                steps=steps, current_index=current_index, rules=rules,
                step=step, rule=rule,
            )

        # Unclear reply: repeat the same add/done prompt unchanged.
        return _collection_stay_put(
            step, current_index,
            presenter.build_collection_prompt(step, current_index, total),
        )

    # stage == "collecting"

    columns = composite_rules.columns_of(step)
    column = columns[progress["column_index"]]

    if input_intent.is_question(value):
        explanation = _explain_for(column, value, step.get("conversation", []))

        if explanation:
            return _collection_stay_put(
                step, current_index,
                presenter.build_step_explanation_message(explanation)
                + presenter.build_collection_prompt(step, current_index, total),
            )

    errors = composite_rules._validate_cell(value, column)

    if errors:
        step["attempts"] = int(step.get("attempts", 0)) + 1

        return _collection_stay_put(
            step, current_index,
            presenter.build_field_problem_message(
                step, current_index, total, column["name"], errors,
            ),
        )

    progress["current_row"].append(value)
    progress["column_index"] += 1

    if progress["column_index"] < len(columns):
        return _collection_stay_put(
            step, current_index,
            presenter.build_collection_prompt(step, current_index, total),
        )

    progress["rows"].append(progress["current_row"])
    progress["current_row"] = []
    progress["stage"] = "row_decision"

    return _collection_stay_put(
        step, current_index,
        presenter.build_collection_prompt(step, current_index, total),
    )


def _take_list_collection_turn(
    *, steps: list[dict], current_index: int, rules: list[dict],
    user_input: str, step: dict, rule: dict,
) -> dict:

    progress = step["composite_progress"]
    value = str(user_input or "").strip()
    total = len(steps)

    if _is_done_keyword(value):

        minimum = composite_rules.minimum_items(step)

        if len(progress["items"]) < minimum:
            return _collection_stay_put(
                step, current_index,
                presenter.build_collection_shortfall_message(
                    step, current_index, total,
                    kind="items", minimum=minimum, have=len(progress["items"]),
                ),
            )

        return _finalize_collection(
            steps=steps, current_index=current_index, rules=rules,
            step=step, rule=rule,
        )

    item_rule = composite_rules.item_rule_of(step)

    if input_intent.is_question(value):
        explanation = _explain_for(item_rule, value, step.get("conversation", []))

        if explanation:
            return _collection_stay_put(
                step, current_index,
                presenter.build_step_explanation_message(explanation)
                + presenter.build_collection_prompt(step, current_index, total),
            )

    errors = composite_rules._validate_cell(value, item_rule)

    if errors:
        step["attempts"] = int(step.get("attempts", 0)) + 1

        return _collection_stay_put(
            step, current_index,
            presenter.build_field_problem_message(
                step, current_index, total,
                f"Item {len(progress['items']) + 1}", errors,
            ),
        )

    progress["items"].append(value)

    return _collection_stay_put(
        step, current_index,
        presenter.build_collection_prompt(step, current_index, total),
    )


def _take_collection_turn(
    *, steps: list[dict], current_index: int, rules: list[dict],
    user_input: str, step: dict, rule: dict,
) -> dict:
    """Dispatch one collection-mode turn to its shape's handler."""

    progress = step["composite_progress"]

    if progress.get("shape") == composite_rules.SHAPE_TABLE:
        return _take_table_collection_turn(
            steps=steps, current_index=current_index, rules=rules,
            user_input=user_input, step=step, rule=rule,
        )

    return _take_list_collection_turn(
        steps=steps, current_index=current_index, rules=rules,
        user_input=user_input, step=step, rule=rule,
    )


def _finalize_collection(
    *, steps: list[dict], current_index: int, rules: list[dict],
    step: dict, rule: dict,
) -> dict:
    """
    Assemble what was collected into the blob a pasted whole answer
    would have been, then judge it through the ordinary take_turn()
    path — so pass/fail, advancing and message wording for the final
    judgment are never duplicated here.

    Cells are joined with "|" because composite_rules._pick_separator
    checks that separator before "," / ";" / tab, so a cell containing
    a comma still round-trips correctly with no parser changes.
    """

    progress = step.get("composite_progress") or {}

    if progress.get("shape") == composite_rules.SHAPE_TABLE:
        blob = "\n".join("|".join(row) for row in progress.get("rows", []))
    else:
        blob = "\n".join(progress.get("items", []))

    step.pop("composite_progress", None)

    result = take_turn(
        steps=steps,
        current_index=current_index,
        rules=rules,
        user_input=blob,
    )

    if not result["passed"]:
        # A cross-field rule failed even though every cell/item passed
        # on its own (the only way the assembled blob can be rejected
        # here). Re-open field-by-field collection rather than asking
        # for a raw paste the user was never shown how to make.
        ensure_collection_started(step)

    return result


# ============================================================
# EDITING AN ALREADY-COMPLETED STEP
# ============================================================

def edit_completed_step(
    *,
    steps: list[dict],
    edit_index: int,
    rules: list[dict],
    user_input: str,
) -> dict:
    """
    Correct an already-completed step's answer.

    A stateless re-judgment of one whole replacement value against the
    step's own rule — the same judgment take_turn() makes for a fresh
    answer, reused rather than duplicated. Composite steps are edited
    as one whole corrected blob (not re-collected field by field):
    editing is a deliberate, low-frequency detour rather than the
    primary flow, and this keeps it a simple, stateless call with no
    "keep previous value vs overwrite per field" ambiguity.

    Never touches current_index, status, or any other step, so the
    walkthrough resumes exactly where it was.
    """

    if not (0 <= edit_index < len(steps)):
        raise ValueError("No step at that position.")

    step = steps[edit_index]

    if step.get("status") != "completed":
        raise ValueError("Only a completed step can be edited.")

    rule = find_rule(rules, step.get("rule_id")) or step

    value = str(user_input or "").strip()
    known_example = str(step.get("suggested_example") or "").strip()

    try:
        verdict = run_rule_workflow(
            rule=rule,
            user_input=value,
            conversation_history=step.get("conversation", []),
            known_example=known_example,
        )
    except GroqNetworkError:
        logger.warning(
            "Groq unreachable while validating edit for step '%s'",
            step.get("rule_name", "unknown"),
        )

        message_blocks = presenter.build_network_error_message(
            step, edit_index, len(steps), example=known_example,
        )

        return {
            "edited": False,
            "step_index": edit_index,
            "step": step,
            "message_blocks": message_blocks,
            "message_lines": presenter.lines_of(message_blocks),
            "verdict": {"status": "network_error", "passed": False},
            "public_verdict": {"status": "network_error", "passed": False},
        }
    except Exception:
        logger.exception(
            "Edit validation failed for step '%s'",
            step.get("rule_name", "unknown"),
        )

        message_blocks = presenter.build_error_message(
            step, edit_index, len(steps), example=known_example,
        )

        return {
            "edited": False,
            "step_index": edit_index,
            "step": step,
            "message_blocks": message_blocks,
            "message_lines": presenter.lines_of(message_blocks),
            "verdict": {"status": "error", "passed": False},
            "public_verdict": {"status": "error", "passed": False},
        }

    if not isinstance(verdict, dict):
        verdict = {"status": "failed", "passed": False, "validation_errors": []}

    passed = verdict.get("status") == "passed"

    if passed:
        step["user_value"] = value
        step["last_verdict"] = verdict

        message_blocks = presenter.build_edit_success_message(
            step, edit_index, len(steps), submitted_value=value,
        )
    else:
        message_blocks = presenter.build_failure_message(
            step, edit_index, len(steps), verdict,
            corrected_example=known_example,
            submitted_value=value,
        )

    record_exchange(
        step,
        value,
        " ".join(presenter.lines_of(message_blocks)[:2]),
    )

    return {
        "edited": passed,
        "step_index": edit_index,
        "step": step,
        "message_blocks": message_blocks,
        "message_lines": presenter.lines_of(message_blocks),
        "verdict": verdict,
        "public_verdict": presenter.public_verdict(verdict),
    }


def record_exchange(step: dict, user_input: str, summary: str) -> list:
    """Append one user/assistant turn to a step's conversation."""

    from datetime import datetime

    conversation = step.get("conversation")

    if not isinstance(conversation, list):
        conversation = []

    now = datetime.now().isoformat()

    conversation.append({
        "sender": "user",
        "text": str(user_input or ""),
        "timestamp": now,
    })

    conversation.append({
        "sender": "ai",
        "text": str(summary or ""),
        "timestamp": now,
    })

    step["conversation"] = conversation

    return conversation
