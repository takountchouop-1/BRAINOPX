"""
skill_engine_service.py

The Rule Engine orchestration layer.

Each uploaded rule triggers its own dedicated AI workflow.

Architecture:

    Uploaded Rules File
            ↓
       extract_text()
            ↓
      parse_rules_to_json()
            ↓
      Structured Rules
            ↓
      SkillEngineRun.rules_json
            ↓
      run_rule_workflow()
            ↓
      deterministic validation
            ↓
       ┌────┴────┐
       │         │
     VALID     INVALID
       │         │
   Next step   Same step
"""

import json
import logging
from datetime import datetime

from fastapi import HTTPException, status

from app.db.models import ConfigurationTask, SkillEngineRun

from app.services.groq_service import (
    parse_rules_to_json,
    run_rule_workflow,
    run_rule_followup,
)

from app.services.rule_parser import extract_text

from app.services.example_utils import (
    build_rules_with_examples,
)

logger = logging.getLogger(__name__)


# ============================================================================
# RULES TEXT EXTRACTION
# ============================================================================


def get_task_rules_text(db, task_id: int) -> str:
    """
    Returns the extracted text from the rules file attached
    to a Skill Engine task.
    """

    task = (
        db.query(ConfigurationTask)
        .filter(
            ConfigurationTask.id == task_id,
            ConfigurationTask.is_active == True,  # noqa: E712
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    if task.category != "skill_engine":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected task is not a Skill Engine task.",
        )

    if not task.template_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This task has no rules file attached.",
        )

    return extract_text(task.template_file_path)


# ============================================================================
# CACHE PARSED RULES
# ============================================================================


def _cache_parsed_rules(
    task,
    rules: list[dict],
    db,
) -> list[dict]:
    """
    Enrich rules with examples and cache the COMPLETE
    structured rules inside category_metadata.parsed_rules.

    The original rule constraints are preserved.
    """

    enriched = build_rules_with_examples(rules)

    metadata = {}

    if task.category_metadata:
        try:
            metadata = json.loads(
                task.category_metadata
            ) or {}
        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            metadata = {}

    metadata["parsed_rules"] = enriched

    task.category_metadata = json.dumps(
        metadata,
        ensure_ascii=False,
    )

    db.commit()

    return enriched


# ============================================================================
# PARSE TASK RULES
# ============================================================================


def parse_task_rules(
    db,
    task_id: int,
) -> list[dict]:
    """
    Parses the uploaded rules document into structured rules.

    IMPORTANT:

    The returned rules must preserve:

        id
        name
        description
        task
        expected_outcome
        data_type
        constraints
        keywords
        example/example_input
    """

    rules_text = get_task_rules_text(
        db,
        task_id,
    )

    rules = parse_rules_to_json(
        rules_text
    )

    if not rules:
        return []

    task = (
        db.query(ConfigurationTask)
        .filter(
            ConfigurationTask.id == task_id
        )
        .first()
    )

    if task:
        return _cache_parsed_rules(
            task,
            rules,
            db,
        )

    return build_rules_with_examples(
        rules
    )


# ============================================================================
# GET RULES FOR TASK
# ============================================================================


def get_rules_for_task(
    db,
    task_id: int,
) -> list[dict]:
    """
    Returns the COMPLETE structured rules for a task.

    Priority:

        1. Cached parsed rules
        2. Uploaded skill-engine rules file
        3. Separate rules document
    """

    task = (
        db.query(ConfigurationTask)
        .filter(
            ConfigurationTask.id == task_id
        )
        .first()
    )

    if not task:
        return []

    # ------------------------------------------------------------------
    # 1. Cached parsed rules
    # ------------------------------------------------------------------

    if task.category_metadata:

        try:

            metadata = json.loads(
                task.category_metadata
            ) or {}

            cached = metadata.get(
                "parsed_rules"
            )

            if cached:

                # IMPORTANT:
                # Do not rebuild the rules from only
                # name/task/keywords.
                #
                # Preserve the complete cached rule.
                return build_rules_with_examples(
                    cached
                )

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            pass

    # ------------------------------------------------------------------
    # 2. Skill Engine uploaded rules file
    # ------------------------------------------------------------------

    if (
        task.category == "skill_engine"
        and task.template_file_path
    ):

        try:

            rules_text = extract_text(
                task.template_file_path
            )

            rules = parse_rules_to_json(
                rules_text
            )

            return _cache_parsed_rules(
                task,
                rules,
                db,
            )

        except Exception:
            logger.exception(
                "Could not read the skill-engine rules file "
                "for task %s",
                task_id,
            )
            return []

    # ------------------------------------------------------------------
    # 3. Separate rules document
    # ------------------------------------------------------------------

    if getattr(
        task,
        "rules_document_path",
        None,
    ):

        try:

            rules_text = extract_text(
                task.rules_document_path
            )

            rules = parse_rules_to_json(
                rules_text
            )

            return _cache_parsed_rules(
                task,
                rules,
                db,
            )

        except Exception:
            logger.exception(
                "Could not read the rules document for task %s",
                task_id,
            )
            return []

    return []


# ============================================================================
# EVALUATE INPUT AGAINST RULES
# ============================================================================


def evaluate_input_against_rules(
    db,
    task_id: int,
    input_text: str,
):
    """
    Runs the deterministic rule workflow for every rule.

    IMPORTANT:
    run_rule_workflow() receives the COMPLETE rule.
    """

    rules = get_rules_for_task(
        db,
        task_id,
    )

    results = []

    for rule in rules:

        verdict = run_rule_workflow(
            rule=rule,
            user_input=input_text,
        )

        verdict["conversation"] = []

        results.append(
            verdict
        )

    return rules, results


# ============================================================================
# RULES CONTEXT
# ============================================================================


def get_rules_context(
    db,
    task_id: int,
    eval_profile_raw: str | None = None,
):
    """
    Builds rules context for the chat AI.
    """

    rules = get_rules_for_task(
        db,
        task_id,
    )

    if not rules:
        return None

    results = []

    if eval_profile_raw:

        try:

            profile = json.loads(
                eval_profile_raw
            ) or {}

            results = (
                profile.get(
                    "rule_results",
                    [],
                )
                or []
            )

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):

            results = []

    return {
        "rules": rules,
        "results": results,
    }


# ============================================================================
# SUMMARY MESSAGE
# ============================================================================


def build_rules_summary_message(
    task_name: str,
    rules: list[dict],
    results: list[dict],
) -> str:
    """
    Builds the response shown after rules are evaluated.
    """

    passed = sum(
        1
        for r in results
        if r.get("status") == "passed"
    )

    total = len(results)

    status_labels = {
        "passed": "Passed",
        "needs_work": "Needs work",
        "failed": "Needs work",
        "not_answered": "Not answered",
    }

    lines = [
        f"I've analysed your file against the rules for '{task_name}'.",
        f"Rules check: {passed}/{total} passed.",
    ]

    for idx, res in enumerate(
        results,
        1,
    ):

        label = status_labels.get(
            res.get("status"),
            res.get("status", "—"),
        )

        lines.append(
            f"\n{idx}. "
            f"{res.get('rule_name', f'Rule {idx}')} "
            f"— {label}"
        )

        if res.get("summary"):
            lines.append(
                f"   {res['summary']}"
            )

        if res.get("next_action"):
            lines.append(
                f"   Next action: "
                f"{res['next_action']}"
            )

        if res.get("guidance"):
            lines.append(
                f"   Guidance: "
                f"{res['guidance']}"
            )

        if res.get("suggested_fix"):
            lines.append(
                f"   Example input: "
                f"{res['suggested_fix']}"
            )

    lines.append(
        "\nTell me which rule you'd like "
        "to work on first, or describe a correction."
    )

    return "\n".join(lines)


# ============================================================================
# START RUN
# ============================================================================


def start_run(
    db,
    *,
    user_id: int,
    task_id: int | None = None,
    rules_file_path: str | None = None,
    input_file_path: str | None = None,
    input_text: str | None = None,
) -> dict:

    """
    Starts a Rule Engine run.

    Rules are always parsed from the uploaded rules document
    and stored in rules_json.
    """

    # ==================================================================
    # 1. RESOLVE RULE SOURCE
    # ==================================================================

    if task_id:

        # Prefer the rules parsed and enriched when the task was
        # created. get_rules_for_task() falls back to re-reading the
        # uploaded document if nothing was cached.

        rules = get_rules_for_task(
            db,
            task_id,
        )

        if not rules:

            rules_text = get_task_rules_text(
                db,
                task_id,
            )

            rules = parse_rules_to_json(
                rules_text
            )

        resolved_task_id = task_id

    elif rules_file_path:

        rules_text = extract_text(
            rules_file_path
        )

        rules = parse_rules_to_json(
            rules_text
        )

        resolved_task_id = None

    else:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Provide either a task_id "
                "or a rules file."
            ),
        )

    if not rules:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No rules could be identified "
                "in the rules document."
            ),
        )

    # Preserve complete rules while adding examples.
    rules = build_rules_with_examples(
        rules
    )

    # ==================================================================
    # 2. USER INPUT
    # ==================================================================

    if input_file_path:

        user_input = extract_text(
            input_file_path
        )

    elif (
        input_text
        and input_text.strip()
    ):

        user_input = input_text.strip()

    else:

        user_input = ""

    # ==================================================================
    # 3. RUN EACH RULE
    # ==================================================================

    results = []

    for rule in rules:

        # Each rule already carries the example generated for it, so
        # evaluating input does not need to rebuild one.

        verdict = run_rule_workflow(
            rule=rule,
            user_input=(
                user_input
                if user_input
                else "(No input provided yet)"
            ),
            known_example=str(
                rule.get("example_input")
                or rule.get("example")
                or ""
            ).strip(),
        )

        verdict["conversation"] = []

        results.append(
            verdict
        )

    # ==================================================================
    # 4. PERSIST
    # ==================================================================

    run_record = SkillEngineRun(
        user_id=user_id,
        task_id=resolved_task_id,
        status="completed",

        rules_json=json.dumps(
            rules,
            ensure_ascii=False,
        ),

        user_input_text=(
            user_input[:50000]
        ),

        results_json=json.dumps(
            {
                "results": results,
                "guided_sessions": {},
            },
            ensure_ascii=False,
        ),

        summary_stats=_compute_stats(
            results
        ),
    )

    db.add(run_record)

    db.commit()

    db.refresh(run_record)

    return serialize_run(
        run_record
    )


# ============================================================================
# GET RUN
# ============================================================================


def get_run(
    db,
    run_id: int,
) -> dict:

    run = (
        db.query(SkillEngineRun)
        .filter(
            SkillEngineRun.id == run_id
        )
        .first()
    )

    if not run:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )

    return serialize_run(
        run
    )


# ============================================================================
# RULE FOLLOW-UP
# ============================================================================


def add_rule_followup(
    db,
    *,
    run_id: int,
    rule_id: int,
    user_message: str,
) -> dict:

    run = (
        db.query(SkillEngineRun)
        .filter(
            SkillEngineRun.id == run_id
        )
        .first()
    )

    if not run:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )

    rules = _load_json(
        run.rules_json,
        [],
    )

    results, metadata = _load_results(
        run.results_json
    )

    # ---------------------------------------------------------------
    # IMPORTANT:
    # Get the ORIGINAL COMPLETE rule.
    # ---------------------------------------------------------------

    rule = next(
        (
            r for r in rules
            if str(r.get("id"))
            == str(rule_id)
        ),
        None,
    )

    if not rule:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found in run.",
        )

    result = next(
        (
            r
            for r in results
            if str(r.get("rule_id"))
            == str(rule_id)
        ),
        None,
    )

    if not result:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule result not found.",
        )

    conversation = (
        result.get("conversation")
        or []
    )

    conversation.append(
        {
            "sender": "user",
            "text": user_message,
            "timestamp": datetime.now().isoformat(),
        }
    )

    ai_reply = run_rule_followup(
        rule=rule,
        user_message=user_message,
        conversation_history=conversation,
        previous_verdict=result,
    )

    conversation.append(
        {
            "sender": "ai",
            "text": ai_reply,
            "timestamp": datetime.now().isoformat(),
        }
    )

    result["conversation"] = conversation

    metadata["results"] = results

    run.results_json = json.dumps(
        metadata,
        ensure_ascii=False,
    )

    run.summary_stats = _compute_stats(
        results
    )

    db.commit()

    return {
        "run_id": run_id,
        "rule_id": rule_id,
        "ai_reply": ai_reply,
        "conversation": conversation,
        "result": result,
    }


# ============================================================================
# RE-EVALUATE ONE RULE
# ============================================================================


def re_evaluate_rule(
    db,
    *,
    run_id: int,
    rule_id: int,
    user_input: str,
) -> dict:

    run = (
        db.query(SkillEngineRun)
        .filter(
            SkillEngineRun.id == run_id
        )
        .first()
    )

    if not run:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found.",
        )

    rules = _load_json(
        run.rules_json,
        [],
    )

    results, metadata = _load_results(
        run.results_json
    )

    # ---------------------------------------------------------------
    # IMPORTANT:
    # Retrieve the COMPLETE ORIGINAL RULE.
    # ---------------------------------------------------------------

    rule = next(
        (
            r for r in rules
            if str(r.get("id"))
            == str(rule_id)
        ),
        None,
    )

    if not rule:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found in run.",
        )

    idx = next(
        (
            i
            for i, r in enumerate(results)
            if str(r.get("rule_id"))
            == str(rule_id)
        ),
        None,
    )

    if idx is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule result not found.",
        )

    conversation = (
        results[idx].get("conversation")
        or []
    )

    conversation.append(
        {
            "sender": "user",
            "text": user_input,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # ---------------------------------------------------------------
    # THE COMPLETE RULE GOES INTO THE WORKFLOW
    # ---------------------------------------------------------------

    verdict = run_rule_workflow(
        rule=rule,
        user_input=user_input,
        conversation_history=conversation,
    )

    verdict["conversation"] = conversation

    results[idx] = verdict

    metadata["results"] = results

    run.results_json = json.dumps(
        metadata,
        ensure_ascii=False,
    )

    run.summary_stats = _compute_stats(
        results
    )

    db.commit()

    return serialize_run(
        run
    )


# ============================================================================
# HELPERS
# ============================================================================


def _load_json(
    raw,
    default,
):
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


def _load_results(
    raw: str,
):
    """
    Supports both:

        [...]
    
    and:

        {
            "results": [...],
            "guided_sessions": {}
        }
    """

    data = _load_json(
        raw,
        [],
    )

    if isinstance(
        data,
        dict,
    ):

        metadata = data

        results = (
            data.get(
                "results",
                [],
            )
            or []
        )

        metadata.setdefault(
            "guided_sessions",
            {},
        )

        return results, metadata

    if isinstance(
        data,
        list,
    ):

        return data, {
            "results": data,
            "guided_sessions": {},
        }

    return [], {
        "results": [],
        "guided_sessions": {},
    }


def _compute_stats(
    results: list[dict],
) -> str:

    total = len(results)

    passed = sum(
        1
        for r in results
        if r.get("status") == "passed"
    )

    needs_work = sum(
        1
        for r in results
        if r.get("status")
        in (
            "needs_work",
            "failed",
        )
    )

    not_answered = sum(
        1
        for r in results
        if r.get("status")
        == "not_answered"
    )

    return json.dumps(
        {
            "total": total,
            "passed": passed,
            "needs_work": needs_work,
            "not_answered": not_answered,
            "progress": (
                round(
                    (passed / total) * 100
                )
                if total
                else 0
            ),
        }
    )


def serialize_run(
    run: SkillEngineRun,
) -> dict:

    results, _ = _load_results(
        run.results_json
    )

    return {
        "id": run.id,
        "task_id": run.task_id,
        "status": run.status,

        "rules": _load_json(
            run.rules_json,
            [],
        ),

        "results": results,

        "summary_stats": _load_json(
            run.summary_stats,
            {},
        ),

        "user_input_text": (
            run.user_input_text
            or ""
        ),

        "created_at": (
            run.created_at.isoformat()
            if run.created_at
            else None
        ),
    }
