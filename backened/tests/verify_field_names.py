"""
A field's name must inform validation, not just the example.

The SALE ORDER transcript showed 'kengne@gmail' accepted at the Email
step but rejected in the Customer Information table — the same field
judged two ways, because the example builder read the name and the
validator read only the constraints.
"""
import os
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from app.services.example_utils import build_example_value
from app.services.groq_service import (
    deterministic_validate_example,
    _get_effective_constraints,
    _infer_semantic_type,
)

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


print("=" * 76)
print("A field named for its format is validated on that format")
print("=" * 76)

for name, semantic in [
    ("Email", "email"),
    ("Customer Email", "email"),
    ("Contact E-Mail", "email"),
    ("Phone", "phone"),
    ("Customer Phone", "phone"),
    ("Mobile Number", "phone"),
]:
    rule = {"name": name, "description": ""}
    got = _infer_semantic_type(rule, _get_effective_constraints(rule))
    check(f"'{name}' recognised as {semantic}", got == semantic, got or "none")

print()
print("=" * 76)
print("The transcript's inputs, now judged the same either way")
print("=" * 76)

CASES = [
    ("Email", "kengne@gmail", False),
    ("Email", "kengne@gmail.com", True),
    ("Phone", "345", False),
    ("Phone", "+237690000001", True),
]

COLUMN_EQUIVALENT = {
    "Email": {"name": "Email", "constraints": {"required": True, "format": "email"}},
    "Phone": {"name": "Phone", "constraints": {"required": True, "format": "phone"}},
}

for name, value, expected in CASES:
    scalar = {"name": name, "description": ""}

    as_step = bool(deterministic_validate_example(example=value, rule=scalar).get("valid"))
    as_cell = bool(deterministic_validate_example(
        example=value, rule=COLUMN_EQUIVALENT[name]).get("valid"))

    check(
        f"{name} '{value}': {'accepted' if expected else 'rejected'} as a step",
        as_step == expected,
        str(as_step),
    )
    check(
        f"{name} '{value}': step and table column agree",
        as_step == as_cell,
        f"step={as_step} column={as_cell}",
    )

print()
print("=" * 76)
print("A leading word must not retype an unrelated field")
print("=" * 76)

for name in ("Email Template", "Phone Support Hours", "Email Frequency"):
    rule = {"name": name, "description": ""}
    got = _infer_semantic_type(rule, _get_effective_constraints(rule))
    check(f"'{name}' not forced to a format", got in ("", "integer", "number"), got or "none")

print()
print("=" * 76)
print("The head noun decides the example, not the longest match")
print("=" * 76)

for name, expected in [
    ("Customer ID", "CUST-0001"),
    ("Customer Name", "Acme Corp"),
    ("Address", "12 Rue Bastos, Yaounde"),
    ("Customer Address", "12 Rue Bastos, Yaounde"),
    ("Email", "user@example.com"),
]:
    got = build_example_value({"name": name, "description": ""})
    check(f"'{name}' -> {expected}", got == expected, got)

print()
print("=" * 76)
print("Every example still passes its own rule")
print("=" * 76)

for name in ("Customer Name", "Customer ID", "Email", "Phone", "Address",
             "Customer Email", "Mobile Number"):
    rule = {"name": name, "description": ""}
    example = build_example_value(rule)
    verdict = deterministic_validate_example(example=example, rule=rule)
    check(
        f"{name}: '{example}' valid",
        bool(verdict.get("valid")),
        "; ".join(verdict.get("errors", []) or []) or "valid",
    )

# --- a vague parser data_type must not disable checks ---
print()
print("=" * 76)
print("A vague data_type from the parser cannot disable validation")
print("=" * 76)

for declared in ("", "text", "string", "varchar", "alphanumeric", "object"):
    rule = {"name": "Email", "description": "", "data_type": declared}
    got = bool(deterministic_validate_example(example="leo", rule=rule).get("valid"))
    check(
        f"Email with data_type={declared!r}: 'leo' rejected",
        got is False,
        "accepted" if got else "rejected",
    )

    prule = {"name": "Phone", "description": "", "data_type": declared}
    pgot = bool(deterministic_validate_example(example="teh", rule=prule).get("valid"))
    check(
        f"Phone with data_type={declared!r}: 'teh' rejected",
        pgot is False,
        "accepted" if pgot else "rejected",
    )

# A meaningful declared type must still win.
for declared, value, expected in [
    ("identifier", "leo", True),
    ("email", "leo", False),
    ("integer", "abc", False),
]:
    rule = {"name": "Field", "description": "", "data_type": declared}
    got = bool(deterministic_validate_example(example=value, rule=rule).get("valid"))
    check(
        f"declared {declared!r} still honoured for {value!r}",
        got == expected,
        str(got),
    )

# Genuine free text stays permissive.
free = {"name": "Comment", "description": "", "data_type": "text"}
check(
    "a real free-text field still accepts short text",
    bool(deterministic_validate_example(example="ok", rule=free).get("valid")),
    "permissive",
)

print()
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
sys.exit(1 if FAIL else 0)
