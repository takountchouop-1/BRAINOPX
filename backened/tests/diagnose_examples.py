"""
For each realistic rule: build the example the assistant would show,
then validate it against that same rule. Any FAIL is an example the
assistant presents as correct but its own validator rejects.
"""
import os
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services.example_utils import build_example_value
from app.services.groq_service import deterministic_validate_example

RULES = [
    # id / name / description
    ("Tariff Code", "Must start with TRF followed by 3 digits"),
    ("Workflow Step ID", "Must be in the format WFS + 3 digits"),
    ("Employee ID", "Must start with EMP followed by 4 digits"),
    ("Operation Code", "Format: SCH + 3 digits"),
    ("Invoice Number", "Must start with INV- followed by 4 digits"),

    ("Status", "Allowed values: ACTIVE, INACTIVE, PENDING"),
    ("Priority", "Must be one of: HIGH, MEDIUM, LOW"),
    ("Currency", "Must be a valid 3 letter ISO currency code"),

    ("Unit Rate", "Must be a positive number with 2 decimal places"),
    ("Tax Rate", "Must be a percentage between 0 and 100"),
    ("Quantity", "Must be a positive integer"),
    ("Total Amount", "Must be a number greater than 0"),

    ("Validity Start Date", "Must be a date in YYYY-MM-DD format"),
    ("Validity End Date", "Must be a valid date after the start date"),
    ("Start Time", "Must be a time in HH:MM format"),

    ("Contact Email", "Must be a valid email address"),
    ("Phone Number", "Must be a valid phone number"),

    ("Tariff Name", "Must be text between 3 and 50 characters"),
    ("Description", "Must not exceed 200 characters"),
    ("Reference Code", "Must be exactly 6 characters"),
    ("Account Code", "Must be exactly 8 digits"),

    ("Is Active", "Must be true or false"),
    ("Step Order", "Must be a sequential number starting from 1"),
    ("Assignee", "Must be a valid user ID"),
    ("Target System", "Must be either PRODUCTION or STAGING"),
]

rows = []
failures = 0

for name, description in RULES:
    rule = {
        "id": len(rows) + 1,
        "name": name,
        "description": description,
    }

    try:
        example = build_example_value(rule)
    except Exception as exc:
        example = f"<error: {exc}>"

    try:
        verdict = deterministic_validate_example(example=example, rule=rule)
        ok = bool(verdict.get("valid"))
        why = "; ".join(verdict.get("errors", []) or [])[:60]
    except Exception as exc:
        ok = False
        why = f"validator error: {exc}"[:60]

    if not ok:
        failures += 1

    rows.append((name, description, example, ok, why))

w1 = max(len(r[0]) for r in rows) + 2
w2 = max(len(str(r[2])) for r in rows) + 2

print(f"{'RULE'.ljust(w1)}{'EXAMPLE SHOWN'.ljust(w2)}{'':4}WHY REJECTED")
print("-" * (w1 + w2 + 4 + 40))

for name, description, example, ok, why in rows:
    mark = "ok  " if ok else "BAD "
    print(f"{name.ljust(w1)}{str(example).ljust(w2)}{mark}{why}")

total = len(rows)
print()
print(f"{total - failures}/{total} examples pass their own rule; {failures} rejected.")
