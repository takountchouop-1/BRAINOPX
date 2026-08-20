"""
End to end, the way a real task is created:

  a rules document is written to disk
      -> extract_text()          reads it
      -> parse_rules_to_json()   turns it into steps      [AI stubbed]
      -> build_rules_with_examples()  gives each step its example
      -> stored on the task
      -> start_run()             builds a run from the stored rules
      -> guided walkthrough      steps through them

The AI parser is stubbed so the test is deterministic and offline;
everything downstream of it is the real code.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, r"e:\BRAINOPX\backened")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import User, ConfigurationTask, SkillEngineRun
from app.services import skill_engine_service as ses
from app.services import rule_router_service as rr
from app.services import example_utils
from app.services.groq_service import deterministic_validate_example

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


RULES_DOCUMENT = """\
TARIFF CONFIGURATION RULES

1. Tariff Code - Must start with TRF followed by 3 digits.
2. Tariff Name - Must be text between 3 and 50 characters.
3. Unit Rate - Must be a positive number with 2 decimal places.
4. Currency - Must be a valid 3 letter ISO currency code.
5. Validity Start Date - Must be a date in YYYY-MM-DD format.
6. Status - Allowed values: ACTIVE, INACTIVE.
"""

# What the AI parser is expected to return for that document.
PARSED = [
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

parse_calls = {"n": 0}


def fake_parse(rules_text, *args, **kwargs):
    parse_calls["n"] += 1
    assert "Tariff Code" in rules_text, "parser did not receive the document text"
    return json.loads(json.dumps(PARSED))


# Stub the AI parser everywhere it is imported.
import app.routers.tasks as tasks_router
ses.parse_rules_to_json = fake_parse
tasks_router.parse_rules_to_json = fake_parse

# build_rules_with_examples() now asks Groq for each rule's example
# (see example_utils.py). Stubbed at the same boundary as the parser
# above, so this test stays deterministic and offline while still
# exercising the real build_rules_with_examples()/_store_rules_with_
# examples() code path — only the network call is faked, and it
# returns the same value the old deterministic builder used to, so
# every assertion below still holds.
import app.services.groq_service as groq_service_module
from app.services.example_utils import build_example_value


def fake_generate_example(rule, max_retries=None):
    example = build_example_value(rule)
    return {
        "success": bool(example),
        "valid": bool(example),
        "source": "ai",
        "example": example,
        "explanation": "stubbed for tests",
        "constraints": {},
        "validation": None,
        "validation_reason": "",
        "attempt": 1,
        "attempts": [],
        "fallback_used": False,
    }


groq_service_module.generate_rule_example_with_retry = fake_generate_example

# ---------------------------------------------------------------- setup
engine = create_engine("sqlite://")
Base.metadata.create_all(bind=engine)
db = sessionmaker(bind=engine)()

user = User(full_name="U", email="u@x.com", hashed_password="x")
db.add(user)
db.commit()

tmpdir = tempfile.mkdtemp()
doc_path = os.path.join(tmpdir, "tariff_rules.txt")
with open(doc_path, "w", encoding="utf-8") as fh:
    fh.write(RULES_DOCUMENT)

print("=" * 76)
print("1. Rules document is read off disk")
print("=" * 76)

from app.services.rule_parser import extract_text

text = extract_text(doc_path)
check("document text extracted", "Tariff Code" in text, f"{len(text)} chars")

print()
print("=" * 76)
print("2. Task creation parses the rules and stores an example per step")
print("=" * 76)

task = ConfigurationTask(
    name="Tariff Setup",
    category="skill_engine",
    template_filename="t.txt",
    template_file_path=doc_path,
    expected_columns="[]",
    rules_document_filename="tariff_rules.txt",
    rules_document_path=doc_path,
    rules_content=json.dumps({"full_text": text}),
    created_by=user.id,
)
db.add(task)
db.commit()
db.refresh(task)

stored = tasks_router._store_rules_with_examples(task, text)
db.commit()
db.refresh(task)

check("task creation returned rules", bool(stored), f"{len(stored)} rules")
check("rules cached on the task", bool(task.category_metadata), "category_metadata set")

cached = json.loads(task.category_metadata or "{}").get("parsed_rules") or []
check("all 6 steps cached", len(cached) == 6, str(len(cached)))

for rule in cached:
    example = rule.get("example_input", "")
    verdict = deterministic_validate_example(example=example, rule=rule)
    check(
        f"  {rule['name']}: stored example '{example}' is valid",
        bool(example) and bool(verdict.get("valid")),
        "; ".join(verdict.get("errors", []) or []) or "valid",
    )

print()
print("=" * 76)
print("3. A run reuses the stored rules instead of re-parsing")
print("=" * 76)

before = parse_calls["n"]

run_payload = ses.start_run(
    db,
    user_id=user.id,
    task_id=task.id,
    input_text="",
)

check(
    "run did not re-parse the document with the AI",
    parse_calls["n"] == before,
    f"{parse_calls['n'] - before} extra parse calls",
)

run = db.query(SkillEngineRun).filter_by(id=run_payload["id"]).first()
run_rules = json.loads(run.rules_json)
check("run carries all 6 steps", len(run_rules) == 6, str(len(run_rules)))
check(
    "every step in the run has an example",
    all(r.get("example_input") for r in run_rules),
    ", ".join(str(r.get("example_input")) for r in run_rules),
)

print()
print("=" * 76)
print("4. Guided walkthrough steps through the uploaded rules")
print("=" * 76)

started = rr.init_guided_session(db, run_id=run.id, user_id=user.id)
sid = started["session"]["session_id"]

check(
    "walkthrough has one step per rule",
    started["session"]["total_steps"] == 6,
    str(started["session"]["total_steps"]),
)

ANSWERS = ["TRF900", "Premium Tariff", "250.75", "EUR", "2027-03-01", "INACTIVE"]
shown = []

for index in range(6):

    if index == 0:
        example = started["session"]["active_rule"]["suggested_example"]
        message = started["initial_message"]
        label = started["session"]["active_rule"]["rule_name"]
    else:
        example = resp["session"]["active_rule"]["suggested_example"]
        message = resp["ai_response"]
        label = resp["session"]["active_rule"]["rule_name"]

    rule = run_rules[index]

    verdict = deterministic_validate_example(example=example, rule=rule)
    check(
        f"step {index + 1} ({label}): example '{example}' fits this step's rule",
        bool(verdict.get("valid")),
        "; ".join(verdict.get("errors", []) or []) or "valid",
    )
    check(
        f"step {index + 1} ({label}): example is in the message shown",
        example in message,
        repr(example),
    )

    shown.append(example)

    resp = rr.process_guided_input(
        db, session_id=sid, user_input=ANSWERS[index], user_id=user.id
    )
    check(
        f"step {index + 1} ({label}): a correct answer advances",
        resp["passed"] is True,
        ANSWERS[index],
    )

check("each step had a distinct example", len(set(shown)) == 6, f"{len(set(shown))} of 6")
check("walkthrough completed", resp["all_completed"] is True, str(resp["all_completed"]))

print()
print("  step examples:", ", ".join(shown))

print()
print("=" * 76)
print("5. A wrong answer explains and corrects, without exposing the rule")
print("=" * 76)

s2 = rr.init_guided_session(db, run_id=run.id, user_id=user.id)["session"]["session_id"]
bad = rr.process_guided_input(db, session_id=s2, user_input="XX1", user_id=user.id)

check("wrong answer rejected", bad["passed"] is False, str(bad["passed"]))
check("explains what is missing", "What is missing" in bad["ai_response"], "present")
check("offers the correct format", "TRF001" in bad["ai_response"], "TRF001")
check(
    "does not quote the rule text",
    "Must start with TRF followed by 3 digits" not in bad["ai_response"],
    "rule hidden",
)

print()
print("=" * 76)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 76)
sys.exit(1 if FAIL else 0)
