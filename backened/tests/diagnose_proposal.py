"""
Reproduce the PROPOSAL walkthrough: narrative document sections rather
than formatted fields. Show what example each gets and how the actual
user inputs from the transcript are judged.
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

SECTIONS = [
    "Client Information",
    "Problem Statement",
    "Solution Offered",
    "Pricing Breakdown",
    "Timeline",
    "Terms and Conditions",
    "Scope of Work",
    "Next Steps",
]

print("=" * 78)
print("EXAMPLE SHOWN per section (no format description, as parsed)")
print("=" * 78)

for name in SECTIONS:
    rule = {"name": name, "description": ""}
    constraints = _get_effective_constraints(rule)
    semantic = _infer_semantic_type(rule, constraints)
    example = build_example_value(rule)
    print(f"  {name:24} example={example!r:24} type={semantic!r:12} {constraints}")

print()
print("=" * 78)
print("USER INPUTS from the transcript, judged")
print("=" * 78)

TRANSCRIPT = [
    ("Client Information", "kengne christ"),
    ("Problem Statement", "response issue"),
    ("Solution Offered", "sms"),
    ("Solution Offered", "communication"),
    ("Pricing Breakdown", "price"),
    ("Timeline", "4-03-2021"),
    ("Timeline", "2026-01-15"),
    ("Terms and Conditions", "x"),
    ("Terms and Conditions", "Payment due within 30 days of invoice."),
]

for name, value in TRANSCRIPT:
    rule = {"name": name, "description": ""}
    verdict = deterministic_validate_example(example=value, rule=rule)
    ok = "accepted" if verdict.get("valid") else "REJECTED"
    why = "; ".join(verdict.get("errors", []) or [])
    print(f"  {name:22} {value!r:42} {ok:9} {why}")
