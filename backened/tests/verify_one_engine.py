"""
Both services must now behave identically, because both run the same
step machine. Drive each with the same rules and the same answers and
compare the decisions.
"""
import json
import os
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import User, SkillEngineRun, ConfigurationTask, ConfigurationRequest
from app.services import rule_router_service as rr
from app.services import step_by_step_service as sbs
from app.services import guided_engine as engine
from app.services.example_utils import build_rules_with_examples

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


RULES = build_rules_with_examples([
    {"id": 1, "name": "Tariff Code",
     "description": "Must start with TRF followed by 3 digits"},
    {"id": 2, "name": "Unit Rate",
     "description": "Must be a positive number with 2 decimal places"},
    {"id": 3, "name": "Status",
     "description": "Allowed values: ACTIVE, INACTIVE"},
])

# (input, expected to pass)
SCRIPT = [
    ("nope", False),
    ("TRF123", True),
    ("abc", False),
    ("45.50", True),
    ("MAYBE", False),
    ("ACTIVE", True),
]

db_engine = create_engine("sqlite://")
Base.metadata.create_all(bind=db_engine)
db = sessionmaker(bind=db_engine)()

user = User(full_name="U", email="u@x.com", hashed_password="x")
db.add(user)
db.commit()

run = SkillEngineRun(
    user_id=user.id, status="completed", rules_json=json.dumps(RULES)
)
task = ConfigurationTask(
    name="T", category="skill_engine", template_filename="t",
    template_file_path="t", expected_columns="[]",
)
db.add_all([run, task])
db.commit()

req = ConfigurationRequest(task_id=task.id, user_id=user.id, status="draft")
db.add(req)
db.commit()

print("=" * 74)
print("Engine A: skill-engine guided session")
print("=" * 74)

started = rr.init_guided_session(db, run_id=run.id, user_id=user.id)
sid = started["session"]["session_id"]

a_results = []
for text, _ in SCRIPT:
    r = rr.process_guided_input(db, session_id=sid, user_input=text, user_id=user.id)
    a_results.append({
        "passed": r["passed"],
        "step_index": r["step_index"],
        "example": r["suggested_example"],
        "all_completed": r["all_completed"],
    })
    print(f"  {text:16} passed={r['passed']!s:5} step={r['step_index']} example={r['suggested_example']!r}")

print()
print("=" * 74)
print("Engine B: configuration-request step workflow")
print("=" * 74)

sbs.init_workflow(req, db, RULES)

b_results = []
for text, _ in SCRIPT:
    r = sbs.process_step_input(req, db, text)
    b_results.append({
        "passed": r["passed"],
        "step_index": r["step_index"],
        "example": r["suggested_example"],
        "all_completed": r["all_completed"],
    })
    print(f"  {text:16} passed={r['passed']!s:5} step={r['step_index']} example={r['suggested_example']!r}")

print()
print("=" * 74)
print("The two must agree")
print("=" * 74)

for i, (text, expected) in enumerate(SCRIPT):
    check(
        f"'{text}': both agree on pass/fail",
        a_results[i]["passed"] == b_results[i]["passed"] == expected,
        f"A={a_results[i]['passed']} B={b_results[i]['passed']} expected={expected}",
    )
    check(
        f"'{text}': both land on the same step",
        a_results[i]["step_index"] == b_results[i]["step_index"],
        f"A={a_results[i]['step_index']} B={b_results[i]['step_index']}",
    )
    check(
        f"'{text}': both offer the same example",
        a_results[i]["example"] == b_results[i]["example"],
        f"A={a_results[i]['example']!r} B={b_results[i]['example']!r}",
    )

check(
    "both finish the walkthrough",
    a_results[-1]["all_completed"] and b_results[-1]["all_completed"],
    f"A={a_results[-1]['all_completed']} B={b_results[-1]['all_completed']}",
)

print()
print("=" * 74)
print("The next step's example is offered on advance (both engines)")
print("=" * 74)

# After 'TRF123' (index 1) the user is on step 2 -> Unit Rate example.
check(
    "engine A shows the next step's example after advancing",
    a_results[1]["example"] == RULES[1]["example_input"],
    f"{a_results[1]['example']!r} vs rule 2 example {RULES[1]['example_input']!r}",
)
check(
    "engine B shows the next step's example after advancing",
    b_results[1]["example"] == RULES[1]["example_input"],
    f"{b_results[1]['example']!r} vs rule 2 example {RULES[1]['example_input']!r}",
)

print()
print("=" * 74)
print("Both drive the same module")
print("=" * 74)

check(
    "rule_router_service uses guided_engine",
    getattr(rr, "engine", None) is engine,
    "shared",
)
check(
    "step_by_step_service uses guided_engine",
    getattr(sbs, "engine", None) is engine,
    "shared",
)
check(
    "neither keeps its own step machine",
    not hasattr(rr, "_prepare_step_example") and not hasattr(rr, "_rule_to_step"),
    "duplicates removed",
)

print()
print("=" * 74)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 74)
sys.exit(1 if FAIL else 0)
