"""
Steps 1-5 of the SALE ORDER walkthrough: named fields whose rule text
carries no explicit format. Show what example each gets, what the
validator derives, and how the transcript's inputs are judged.
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

# As a light parse would produce them: a name, no stated format.
FIELDS = [
    ("Customer Name", ""),
    ("Customer ID", ""),
    ("Email", ""),
    ("Phone", ""),
    ("Address", ""),
]

print("=" * 82)
print("SCALAR STEPS 1-5 as parsed")
print("=" * 82)
print(f"  {'FIELD':16} {'EXAMPLE SHOWN':22} {'TYPE':10} CONSTRAINTS")

for name, description in FIELDS:
    rule = {"name": name, "description": description}
    constraints = _get_effective_constraints(rule)
    semantic = _infer_semantic_type(rule, constraints)
    example = build_example_value(rule)
    print(f"  {name:16} {example!r:22} {semantic!r:10} {constraints}")

print()
print("=" * 82)
print("THE TRANSCRIPT'S INPUTS, judged as scalar steps")
print("=" * 82)

TRANSCRIPT = [
    ("Customer Name", "softronic coperation"),
    ("Customer ID", "CUST-2341"),
    ("Email", "kengne@gmail"),
    ("Phone", "345"),
    ("Address", "ewq"),
]

for name, value in TRANSCRIPT:
    rule = {"name": name, "description": ""}
    verdict = deterministic_validate_example(example=value, rule=rule)
    status = "accepted" if verdict.get("valid") else "REJECTED"
    why = "; ".join(verdict.get("errors", []) or [])
    print(f"  {name:16} {value!r:24} {status:9} {why}")

print()
print("=" * 82)
print("THE SAME VALUES as table columns (step 6), where they were rejected")
print("=" * 82)

COLUMNS = [
    {"name": "Customer Name", "constraints": {"required": True}},
    {"name": "Customer ID",
     "constraints": {"required": True, "prefix": "CUST-", "prefix_digit_count": 4}},
    {"name": "Email", "constraints": {"required": True, "format": "email"}},
    {"name": "Phone", "constraints": {"required": True, "format": "phone"}},
    {"name": "Address", "constraints": {"required": True}},
]

for column, (_, value) in zip(COLUMNS, TRANSCRIPT):
    verdict = deterministic_validate_example(example=value, rule=column)
    status = "accepted" if verdict.get("valid") else "REJECTED"
    why = "; ".join(verdict.get("errors", []) or [])
    print(f"  {column['name']:16} {value!r:24} {status:9} {why}")

print()
print("=" * 82)
print("WHERE THE EXAMPLE COMES FROM vs WHERE VALIDATION COMES FROM")
print("=" * 82)

for name in ("Email", "Phone", "Address", "Customer ID"):
    rule = {"name": name, "description": ""}
    constraints = _get_effective_constraints(rule)
    print(
        f"  {name:14} example={build_example_value(rule)!r:22} "
        f"but validator sees {constraints}"
    )
