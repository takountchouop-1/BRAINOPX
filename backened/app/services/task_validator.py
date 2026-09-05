"""
task_validator.py

Checks a parsed task definition — the rules list produced by
groq_service.parse_rules_to_json() and enriched by
example_utils.build_rules_with_examples() — for rules the guided
engine cannot judge reliably, before the task is ever handed to an
end user.

A rule with no usable constraints, no recognized semantic type, and
no narrative/composite shape is the root cause of the AI showing a
wrong example ("ABC-1234" instead of "NOT001"): validation silently
falls through to weak generic checks and the example generator has
nothing concrete to anchor on. This module names that class of rule
at authoring time instead of letting a user discover it mid-walkthrough.

This is a flag, not a gate: a task with issues still saves and
activates normally (see tasks.py::_store_rules_with_examples) — the
report is attached to the task so the admin who authored it can go
back and tighten the source document.
"""

from app.services import composite_rules
from app.services.groq_service import (
    _get_effective_constraints,
    _infer_semantic_type,
    _KNOWN_SEMANTIC_TYPES,
)

# Every rule carries "required": True by default (deterministic_validate_example
# defaults it), so that key alone says nothing about whether the rule is
# judgeable — it is ignored when deciding if a scalar rule has real constraints.
_NON_SUBSTANTIVE_CONSTRAINT_KEYS = {"required"}


def _has_real_constraints(constraints: dict) -> bool:
    if not isinstance(constraints, dict):
        return False

    for key, value in constraints.items():
        if key in _NON_SUBSTANTIVE_CONSTRAINT_KEYS:
            continue
        if value not in (None, "", [], {}):
            return True

    return False


def _validate_one_rule(rule: dict, index: int) -> list[str]:
    """Problems found with a single rule. Empty list means it's fine."""

    problems = []

    if not isinstance(rule, dict):
        return ["Rule is not a structured object."]

    name = str(rule.get("name") or "").strip()
    if not name:
        problems.append("Rule has no name.")

    task_text = str(rule.get("task") or rule.get("description") or "").strip()
    if not task_text:
        problems.append("Rule has no task/description to show the user.")

    shape = composite_rules.input_shape(rule)

    if shape == composite_rules.SHAPE_TABLE:
        if not composite_rules.columns_of(rule):
            problems.append(
                "Table rule has no columns — each column needs its own "
                "description and constraints."
            )
        return problems

    if shape == composite_rules.SHAPE_LIST:
        if not composite_rules.item_rule_of(rule):
            problems.append(
                "List rule has no item_rule describing what one entry "
                "must satisfy."
            )
        return problems

    if shape == composite_rules.SHAPE_NARRATIVE:
        # Narrative rules are judged on word count alone by design —
        # nothing else to check here.
        return problems

    # Scalar rule: it must be judgeable by SOME concrete signal —
    # explicit constraints, or a semantic type the validator
    # recognizes (email, phone, date, identifier, ...).
    constraints = _get_effective_constraints(rule)

    if _has_real_constraints(constraints):
        return problems

    semantic_type = _infer_semantic_type(rule, constraints)

    if semantic_type in _KNOWN_SEMANTIC_TYPES:
        return problems

    problems.append(
        "Rule has no usable constraints and no recognized value type — "
        "the AI has nothing concrete to validate against and may "
        "produce inconsistent examples. Add a format, allowed values, "
        "or a length/range to the source text for this rule."
    )

    return problems


def validate_task_definition(rules: list[dict] | None) -> dict:
    """
    Validate a task's full rule list.

    Returns:
        valid        True when every rule is judgeable
        issue_count  number of rules with at least one problem
        issues       [{"step": i, "rule_name": ..., "problems": [...]}]
    """

    issues = []

    for index, rule in enumerate(rules or []):
        problems = _validate_one_rule(rule, index)

        if problems:
            issues.append({
                "step": index,
                "rule_name": str((rule or {}).get("name") or f"Rule {index + 1}"),
                "problems": problems,
            })

    return {
        "valid": not issues,
        "issue_count": len(issues),
        "issues": issues,
    }
