"""
Table, list and narrative steps: example generation, per-cell
validation, and a full walkthrough mixing all four shapes.
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
from app.services import composite_rules as cr
from app.services import step_presenter as presenter
from app.services.example_utils import build_example_value, build_rules_with_examples
from app.services.groq_service import deterministic_validate_example

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


TABLE_RULE = {
    "id": 1,
    "name": "Tariff Lines",
    "description": "Provide one row per tariff.",
    "input_shape": "table",
    "min_rows": 1,
    "columns": [
        {"name": "Tariff Code", "description": "Must start with TRF followed by 3 digits",
         "constraints": {"required": True, "prefix": "TRF", "prefix_digit_count": 3}},
        {"name": "Unit Rate", "description": "A positive number with 2 decimal places",
         "constraints": {"required": True, "format": "number", "min_value": 0}},
        {"name": "Currency", "description": "Must be USD or XAF",
         "constraints": {"required": True, "allowed_values": ["USD", "XAF"]}},
    ],
}

LIST_RULE = {
    "id": 2,
    "name": "Authorised Approvers",
    "description": "List the employee ID of every approver.",
    "input_shape": "list",
    "min_items": 2,
    "item_rule": {
        "name": "Employee ID",
        "description": "Must start with EMP followed by 4 digits",
        "constraints": {"required": True, "prefix": "EMP", "prefix_digit_count": 4},
    },
}

print("=" * 76)
print("Shape detection")
print("=" * 76)

check("declared table detected", cr.input_shape(TABLE_RULE) == "table", cr.input_shape(TABLE_RULE))
check("declared list detected", cr.input_shape(LIST_RULE) == "list", cr.input_shape(LIST_RULE))
check(
    "undeclared table inferred from wording",
    cr.input_shape({"name": "Lines", "description": "Provide one row per tariff line."}) == "table",
    cr.input_shape({"name": "Lines", "description": "Provide one row per tariff line."}),
)
check(
    "plain field stays scalar",
    cr.input_shape({"name": "Tariff Code", "description": "Must start with TRF and 3 digits"}) == "scalar",
    cr.input_shape({"name": "Tariff Code", "description": "Must start with TRF and 3 digits"}),
)
check(
    "narrative stays narrative",
    cr.input_shape({"name": "Problem Statement", "description": ""}) != "table",
    cr.input_shape({"name": "Problem Statement", "description": ""}),
)

print()
print("=" * 76)
print("Examples show the whole shape")
print("=" * 76)

table_example = build_example_value(TABLE_RULE)
print("  table example:")
for line in table_example.splitlines():
    print("     ", line)

check("table example has a header + 2 rows", len(table_example.splitlines()) == 3,
      f"{len(table_example.splitlines())} lines")
check("header names the columns", table_example.splitlines()[0] == "Tariff Code, Unit Rate, Currency",
      table_example.splitlines()[0])
check("sample rows differ", table_example.splitlines()[1] != table_example.splitlines()[2], "varied")
check("table example passes its own rule",
      bool(deterministic_validate_example(example=table_example, rule=TABLE_RULE).get("valid")),
      "; ".join(deterministic_validate_example(example=table_example, rule=TABLE_RULE).get("errors", []) or []) or "valid")

list_example = build_example_value(LIST_RULE)
print("  list example:", repr(list_example))
check("list example has 3 entries", len(list_example.splitlines()) == 3, f"{len(list_example.splitlines())}")
check("list example passes its own rule",
      bool(deterministic_validate_example(example=list_example, rule=LIST_RULE).get("valid")),
      "; ".join(deterministic_validate_example(example=list_example, rule=LIST_RULE).get("errors", []) or []) or "valid")

print()
print("=" * 76)
print("What to provide names the columns, not the rules")
print("=" * 76)

line = presenter.what_to_provide(TABLE_RULE)
print("  ", line)
check("mentions one row per line", "one row per line" in line, line)
check("names every column", all(c["name"] in line for c in TABLE_RULE["columns"]), line)
check("does not leak a column's rule", "3 digits" not in line and "USD" not in line, line)

print()
print("=" * 76)
print("Per-cell validation, with the row named")
print("=" * 76)

good = "TRF001, 120.00, USD\nTRF002, 85.50, XAF"
verdict = deterministic_validate_example(example=good, rule=TABLE_RULE)
check("valid table accepted", bool(verdict.get("valid")), good.replace("\n", " | "))

with_header = "Tariff Code, Unit Rate, Currency\nTRF001, 120.00, USD"
check("a pasted header row is ignored",
      bool(deterministic_validate_example(example=with_header, rule=TABLE_RULE).get("valid")),
      "header skipped")

check("pipe separated rows accepted",
      bool(deterministic_validate_example(example="TRF001 | 120.00 | USD", rule=TABLE_RULE).get("valid")),
      "pipes")

bad = "TRF001, 120.00, USD\nTRF2, abc, EUR"
verdict = deterministic_validate_example(example=bad, rule=TABLE_RULE)
errors = verdict.get("errors", [])
print("  errors for a bad row:")
for e in errors:
    print("     ", e)

check("bad table rejected", not verdict.get("valid"), "rejected")
check("names the row", any("Row 2" in e for e in errors), "; ".join(errors)[:60])
check("names the column", any("Tariff Code" in e for e in errors), "; ".join(errors)[:60])
check("reports each bad cell", len([e for e in errors if "Row 2" in e]) >= 3, f"{len(errors)} errors")

short = "TRF001, 120.00"
errors = deterministic_validate_example(example=short, rule=TABLE_RULE).get("errors", [])
check("wrong cell count explained", any("expected 3 values" in e for e in errors), "; ".join(errors)[:70])

errors = deterministic_validate_example(example="EMP0001", rule=LIST_RULE).get("errors", [])
check("too few list items explained", any("at least 2" in e for e in errors), "; ".join(errors)[:70])

errors = deterministic_validate_example(example="EMP0001\nEMP2", rule=LIST_RULE).get("errors", [])
check("bad list item names its position", any("Item 2" in e for e in errors), "; ".join(errors)[:70])

print()
print("=" * 76)
print("More than two problems are reported for a table")
print("=" * 76)

verdict = {"validation_errors": [f"Row {i}, Col: bad" for i in range(1, 7)], "problem_limit": 6}
check("presenter honours the raised cap", len(presenter.problems_from(verdict)) == 6,
      f"{len(presenter.problems_from(verdict))} shown")
check("scalar steps still capped at 2",
      len(presenter.problems_from({"validation_errors": ["a", "b", "c"]})) == 2,
      "2")

print()
print("=" * 76)
print("A walkthrough mixing all four shapes")
print("=" * 76)

rules = build_rules_with_examples([
    {"id": 1, "name": "Tariff Code", "description": "Must start with TRF followed by 3 digits"},
    dict(TABLE_RULE, id=2),
    dict(LIST_RULE, id=3),
    {"id": 4, "name": "Terms and Conditions", "description": ""},
])

for rule in rules:
    check(
        f"{rule['name']}: stored example valid for its shape",
        bool(deterministic_validate_example(
            example=rule["example_input"], rule=rule).get("valid")),
        rule["example_input"].replace("\n", " / ")[:56],
    )

db_engine = create_engine("sqlite://")
Base.metadata.create_all(bind=db_engine)
db = sessionmaker(bind=db_engine)()
user = User(full_name="U", email="u@x.com", hashed_password="x")
db.add(user)
db.commit()
run = SkillEngineRun(user_id=user.id, status="completed", rules_json=json.dumps(rules))
db.add(run)
db.commit()

started = rr.init_guided_session(db, run_id=run.id, user_id=user.id)
sid = started["session"]["session_id"]

ANSWERS = [
    "TRF900",
    "TRF010, 99.99, USD\nTRF011, 45.00, XAF",
    "EMP1234\nEMP5678",
    "Payment is due within 30 days of invoice.",
]

for index, answer in enumerate(ANSWERS):
    resp = rr.process_guided_input(db, session_id=sid, user_input=answer, user_id=user.id)
    check(
        f"step {index + 1} ({rules[index]['name']}): correct answer accepted",
        resp["passed"] is True,
        answer.replace("\n", " / ")[:44],
    )

check("walkthrough completed", resp["all_completed"] is True, str(resp["all_completed"]))

print()
print("=" * 76)
print("A table example survives HTML rendering")
print("=" * 76)

s2 = rr.init_guided_session(db, run_id=run.id, user_id=user.id)["session"]["session_id"]
rr.process_guided_input(db, session_id=s2, user_input="TRF900", user_id=user.id)
bad_resp = rr.process_guided_input(db, session_id=s2, user_input="TRF2, abc, EUR", user_id=user.id)

html_out = bad_resp["ai_response"]

check("table rows kept as separate lines in HTML",
      "<br>" in html_out, "line breaks present")
check("row-level error shown to the user",
      "Row 1" in html_out, "row named")

# Any surviving newline must sit inside a pre-wrap block, where it
# renders as a line break. A newline in ordinary flow would collapse.
prose = html_out
for block in prose.split("white-space:pre-wrap;'>")[1:]:
    prose = prose.replace(block.split("</div>")[0], "")

check("no newline left in ordinary flow to collapse",
      "\n" not in prose,
      "newlines only inside pre-wrap")

print()
print("=" * 76)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 76)
sys.exit(1 if FAIL else 0)
