"""
The three defects the tariff transcript shows:

  1. 'Valid Tax Rate' offered 120.00 - a rate, not a percentage
  2. '17-3-3432' accepted as a Future Start Date
  3. '12' accepted where the example demonstrates 2 decimal places
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

RULES = [
    ("Positive Unit Rate", "Must be a positive number with 2 decimal places"),
    ("Valid Tax Rate", "Must be a percentage between 0 and 100"),
    ("Future Start Date", "Must be a date in YYYY-MM-DD format and in the future"),
    ("Valid End Date", "Must be a valid date after the start date"),
]

print("=" * 84)
print("EXAMPLES OFFERED")
print("=" * 84)
for name, description in RULES:
    rule = {"name": name, "description": description}
    constraints = _get_effective_constraints(rule)
    print(f"  {name:22} example={build_example_value(rule)!r:16} "
          f"type={_infer_semantic_type(rule, constraints)!r:10} {constraints}")

print()
print("=" * 84)
print("WHAT THE TRANSCRIPT ENTERED")
print("=" * 84)

CASES = [
    ("Positive Unit Rate", "Must be a positive number with 2 decimal places", "12", "should reject: no decimals"),
    ("Positive Unit Rate", "Must be a positive number with 2 decimal places", "120.00", "should accept"),
    ("Positive Unit Rate", "Must be a positive number with 2 decimal places", "bh", "should reject: not a number"),
    ("Valid Tax Rate", "Must be a percentage between 0 and 100", "11", "should accept"),
    ("Valid Tax Rate", "Must be a percentage between 0 and 100", "120.00", "should reject: over 100"),
    ("Future Start Date", "Must be a date in YYYY-MM-DD format and in the future", "17-3-3432", "should reject: not YYYY-MM-DD"),
    ("Future Start Date", "Must be a date in YYYY-MM-DD format and in the future", "34", "should reject"),
    ("Future Start Date", "Must be a date in YYYY-MM-DD format and in the future", "2027-03-01", "should accept"),
    ("Future Start Date", "Must be a date in YYYY-MM-DD format and in the future", "2020-01-01", "should reject: past"),
]

for name, description, value, expectation in CASES:
    rule = {"name": name, "description": description}
    verdict = deterministic_validate_example(example=value, rule=rule)
    status = "accepted" if verdict.get("valid") else "REJECTED"
    why = "; ".join(verdict.get("errors", []) or [])
    print(f"  {name:20} {value!r:12} {status:9} | {expectation:34} {why}")

print()
print("=" * 84)
print("WHAT THE VALIDATOR CONSIDERS A DATE")
print("=" * 84)

date_rule = {"name": "Start Date", "description": "Must be a date in YYYY-MM-DD format"}
for value in ["2026-01-15", "17-3-3432", "34", "2026-13-45", "15/01/2026", "abcd-ef-gh"]:
    verdict = deterministic_validate_example(example=value, rule=date_rule)
    print(f"  {value!r:14} {'accepted' if verdict.get('valid') else 'REJECTED':9} "
          f"{'; '.join(verdict.get('errors', []) or [])}")
