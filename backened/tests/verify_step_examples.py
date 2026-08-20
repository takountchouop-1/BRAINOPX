"""
Walk a realistic multi-step task end to end and assert that at EVERY
step the assistant shows an example that is (a) present, (b) correct
for that step's rule, and (c) distinct from the previous step's.

Rules go through the real path: build_rules_with_examples() at task
creation, then the guided session.
"""
import json
import os
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import User, SkillEngineRun
from app.services import rule_router_service as rr
from app.services.example_utils import build_rules_with_examples
from app.services.groq_service import deterministic_validate_example

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


RAW_RULES = [
    {"id": 1, "name": "Tariff Code",
     "description": "Must start with TRF followed by 3 digits"},
    {"id": 2, "name": "Tariff Name",
     "description": "Must be text between 3 and 50 characters"},
    {"id": 3, "name": "Unit Rate",
     "description": "Must be a positive number with 2 decimal places"},
    {"id": 4, "name": "Currency",
     "description": "Must be a valid 3 letter ISO currency code"},
    {"id": 5, "name": "Validity Start Date",
     "description": "Must be a date in YYYY-MM-DD format"},
    {"id": 6, "name": "Status",
     "description": "Allowed values: ACTIVE, INACTIVE"},
]

# Correct answers a user might type, per step.
ANSWERS = ["TRF900", "Premium Tariff", "250.75", "EUR", "2027-03-01", "INACTIVE"]

rules = build_rules_with_examples(RAW_RULES)

print("=" * 76)
print("Examples baked in at task creation")
print("=" * 76)

for rule in rules:
    example = rule.get("example_input", "")
    verdict = deterministic_validate_example(example=example, rule=rule)
    check(
        f"{rule['name']}: example '{example}' is valid for its own rule",
        bool(verdict.get("valid")),
        "; ".join(verdict.get("errors", []) or []) or "valid",
    )

engine = create_engine("sqlite://")
Base.metadata.create_all(bind=engine)
db = sessionmaker(bind=engine)()

user = User(full_name="U", email="u@x.com", hashed_password="x")
db.add(user)
db.commit()

run = SkillEngineRun(
    user_id=user.id,
    status="completed",
    rules_json=json.dumps(rules),
)
db.add(run)
db.commit()

print()
print("=" * 76)
print("Walking the session: every step must show its own valid example")
print("=" * 76)

started = rr.init_guided_session(db, run_id=run.id, user_id=user.id)
sid = started["session"]["session_id"]

seen = []
total = len(rules)

for index in range(total):

    if index == 0:
        shown = started["session"]["active_rule"]["suggested_example"]
        message = started["initial_message"]
    else:
        shown = response["session"]["active_rule"]["suggested_example"]
        message = response["ai_response"]

    rule = rules[index]
    name = rule["name"]

    check(
        f"step {index + 1} ({name}): an example is shown",
        bool(shown),
        repr(shown),
    )

    verdict = deterministic_validate_example(example=shown, rule=rule)
    check(
        f"step {index + 1} ({name}): example matches THIS step's rule",
        bool(verdict.get("valid")),
        f"{shown!r} -> " + ("; ".join(verdict.get("errors", []) or []) or "valid"),
    )

    check(
        f"step {index + 1} ({name}): example appears in the message",
        shown in message,
        repr(shown),
    )

    if seen:
        check(
            f"step {index + 1} ({name}): example is not the previous step's",
            shown != seen[-1],
            f"{seen[-1]!r} -> {shown!r}",
        )

    seen.append(shown)

    response = rr.process_guided_input(
        db,
        session_id=sid,
        user_input=ANSWERS[index],
        user_id=user.id,
    )

    check(
        f"step {index + 1} ({name}): correct answer accepted",
        response["passed"] is True,
        ANSWERS[index],
    )

print()
print("=" * 76)
print("Example shown per step")
print("=" * 76)
for rule, example in zip(rules, seen):
    print(f"  {rule['name']:22} {example}")

check(
    "every step showed a distinct example",
    len(set(seen)) == len(seen),
    f"{len(set(seen))} distinct of {len(seen)}",
)
check("walkthrough completed", response["all_completed"] is True, str(response["all_completed"]))

print()
print("=" * 76)
print("A wrong answer is corrected with THIS step's example")
print("=" * 76)

started2 = rr.init_guided_session(db, run_id=run.id, user_id=user.id)
sid2 = started2["session"]["session_id"]

rr.process_guided_input(db, session_id=sid2, user_input="TRF001", user_id=user.id)
bad = rr.process_guided_input(db, session_id=sid2, user_input="!!", user_id=user.id)

check("wrong answer rejected", bad["passed"] is False, str(bad["passed"]))
check(
    "correction is the current step's example, not step 1's",
    bad["suggested_example"] == seen[1],
    f"{bad['suggested_example']!r} (step 2 example {seen[1]!r})",
)
check(
    "correction appears in the message",
    bad["suggested_example"] in bad["ai_response"],
    repr(bad["suggested_example"]),
)

print()
print("=" * 76)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 76)
sys.exit(1 if FAIL else 0)
