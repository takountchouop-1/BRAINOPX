"""
Document sections (prose) must get a sample sentence and be validated
on substance. Formatted fields must be unaffected.
"""
import os
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services.example_utils import build_example_value, build_rules_with_examples
from app.services.groq_service import (
    deterministic_validate_example,
    _get_effective_constraints,
)

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


SECTIONS = [
    "Client Information", "Problem Statement", "Solution Offered",
    "Pricing Breakdown", "Timeline", "Terms and Conditions",
    "Scope of Work", "Next Steps",
]

print("=" * 76)
print("No placeholder is ever shown as an example")
print("=" * 76)

for name in SECTIONS:
    rule = {"name": name, "description": ""}
    example = build_example_value(rule)

    check(
        f"{name}: example is not a placeholder code",
        "VALID001" not in example and example.strip() != "",
        example[:52] + ("..." if len(example) > 52 else ""),
    )
    check(
        f"{name}: example is prose, not a code",
        len(example.split()) >= 3,
        f"{len(example.split())} words",
    )
    verdict = deterministic_validate_example(example=example, rule=rule)
    check(
        f"{name}: the example itself would be accepted",
        bool(verdict.get("valid")),
        "; ".join(verdict.get("errors", []) or []) or "valid",
    )

print()
print("=" * 76)
print("Substance is required, consistently")
print("=" * 76)

rule = {"name": "Solution Offered", "description": ""}

for value, expected in [
    ("sms", False),
    ("communication", False),
    ("price", False),
    ("response issue", False),
    ("Deploy an SMS gateway that answers every request in one minute.", True),
]:
    verdict = deterministic_validate_example(example=value, rule=rule)
    got = bool(verdict.get("valid"))
    check(
        f"'{value[:38]}' {'accepted' if expected else 'rejected'}",
        got == expected,
        "; ".join(verdict.get("errors", []) or []) or "valid",
    )

print()
print("=" * 76)
print("The rejection message says what to do")
print("=" * 76)

verdict = deterministic_validate_example(example="sms", rule=rule)
errors = " ".join(verdict.get("errors", []) or [])
check("message states the shortfall", "at least 3 words" in errors, errors)
check("message reports what was entered", "You entered 1" in errors, errors)
check(
    "no longer calls a real abbreviation gibberish",
    "appears to be invalid" not in errors,
    errors,
)

print()
print("=" * 76)
print("Abbreviations are not rejected as gibberish")
print("=" * 76)

for value in ["SMS", "CRM", "VAT", "SLA"]:
    code_rule = {"name": "System Code", "description": "Allowed values: SMS, CRM, VAT, SLA"}
    verdict = deterministic_validate_example(example=value, rule=code_rule)
    check(
        f"'{value}' accepted against its allowed values",
        bool(verdict.get("valid")),
        "; ".join(verdict.get("errors", []) or []) or "valid",
    )

print()
print("=" * 76)
print("Formatted fields are NOT treated as narrative")
print("=" * 76)

FORMATTED = [
    ("Tariff Code", "Must start with TRF followed by 3 digits", "TRF001"),
    ("Status", "Allowed values: ACTIVE, INACTIVE", "ACTIVE"),
    ("Unit Rate", "Must be a positive number with 2 decimal places", "120.00"),
    ("Contact Email", "Must be a valid email address", "user@example.com"),
    # Dates are generated relative to today, so assert the shape
    # rather than a fixed value that would expire.
    ("Start Date", "Must be a date in YYYY-MM-DD format", "<iso-date>"),
]

for name, description, expected in FORMATTED:
    rule = {"name": name, "description": description}
    constraints = _get_effective_constraints(rule)

    check(
        f"{name}: not marked narrative",
        constraints.get("content_type") != "narrative",
        str(constraints.get("content_type")),
    )
    import re as _re

    produced = build_example_value(rule)

    check(
        f"{name}: example unchanged",
        bool(_re.fullmatch(r"\d{4}-\d{2}-\d{2}", produced))
        if expected == "<iso-date>"
        else produced == expected,
        build_example_value(rule),
    )

print()
print("=" * 76)
print("A full proposal, enriched at task creation")
print("=" * 76)

rules = build_rules_with_examples([
    {"id": i + 1, "name": name, "description": ""}
    for i, name in enumerate(SECTIONS)
])

for rule in rules:
    example = rule["example_input"]
    verdict = deterministic_validate_example(example=example, rule=rule)
    check(
        f"{rule['name']}: stored example valid and readable",
        bool(verdict.get("valid")) and "VALID001" not in example,
        example[:56] + ("..." if len(example) > 56 else ""),
    )

print()
print("=" * 76)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 76)
sys.exit(1 if FAIL else 0)
