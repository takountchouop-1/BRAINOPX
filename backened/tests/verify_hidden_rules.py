"""
Plant sentinel strings in every internal rule field, run the whole
guided flow, and assert no sentinel ever reaches the user.
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

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


# Every internal field gets a sentinel. None may ever be shown.
SENTINELS = {
    "description": "SENTINEL_DESCRIPTION",
    "task": "SENTINEL_TASK",
    "expected_outcome": "SENTINEL_EXPECTED_OUTCOME",
    "constraint_key": "SENTINEL_CONSTRAINT_KEY",
    "constraint_val": "SENTINEL_CONSTRAINT_VALUE",
    "keyword": "SENTINEL_KEYWORD",
    "data_type": "SENTINEL_DATATYPE",
}

RULES = [
    {
        "id": 1,
        "name": "Tariff Code",
        "description": "SENTINEL_DESCRIPTION must start with TRF and 3 digits",
        "task": "SENTINEL_TASK",
        "expected_outcome": "SENTINEL_EXPECTED_OUTCOME",
        "data_type": "SENTINEL_DATATYPE",
        "keywords": ["SENTINEL_KEYWORD"],
        "constraints": {
            "prefix": "TRF",
            "digits_after_prefix": 3,
            "SENTINEL_CONSTRAINT_KEY": "SENTINEL_CONSTRAINT_VALUE",
        },
        "example_input": "TRF001",
    },
    {
        "id": 2,
        "name": "Unit Rate",
        "description": "SENTINEL_DESCRIPTION must be a positive number",
        "task": "SENTINEL_TASK",
        "expected_outcome": "SENTINEL_EXPECTED_OUTCOME",
        "keywords": ["SENTINEL_KEYWORD"],
        "constraints": {"SENTINEL_CONSTRAINT_KEY": "SENTINEL_CONSTRAINT_VALUE"},
        "example_input": "120.00",
    },
]


def scan(payload, label):
    """Assert no sentinel appears anywhere in a response payload."""
    blob = json.dumps(payload, default=str)
    hits = sorted({s for s in SENTINELS.values() if s in blob})
    check(
        f"{label}: no internal rule data",
        not hits,
        ", ".join(hits) if hits else "clean",
    )
    return blob


engine = create_engine("sqlite://")
Base.metadata.create_all(bind=engine)
db = sessionmaker(bind=engine)()

user = User(full_name="U", email="u@x.com", hashed_password="x")
db.add(user)
db.commit()

run = SkillEngineRun(
    user_id=user.id,
    status="completed",
    rules_json=json.dumps(RULES),
    results_json=None,
)
db.add(run)
db.commit()

print("=" * 72)
print("STEP 1 — start: shows step, what to provide, example")
print("=" * 72)

started = rr.init_guided_session(db, run_id=run.id, user_id=user.id)
sid = started["session"]["session_id"]

scan(started, "init_guided_session")

msg = started["initial_message"]
check("shows the step heading", "Step 1 of 2" in msg, "Step 1 of 2")
check("shows what to provide", "Enter the Tariff Code" in msg, "Enter the Tariff Code")
check("shows an example input", "TRF001" in msg, "TRF001")
check(
    "active_rule exposes what_to_provide, not the rule",
    "what_to_provide" in started["session"]["active_rule"]
    and "rule_description" not in started["session"]["active_rule"],
    str(sorted(started["session"]["active_rule"].keys())),
)

print()
print("=" * 72)
print("STEP 2 — invalid input: problem + correction, no rule")
print("=" * 72)

bad = rr.process_guided_input(db, session_id=sid, user_input="WRONG9", user_id=user.id)
scan(bad, "invalid submission")

resp = bad["ai_response"]
check("says it was not accepted", "not accepted" in resp, "not accepted")
check("says what is missing", "What is missing" in resp, "What is missing")
check("names the actual problem", "must start with" in resp, "must start with 'TRF'")
check("offers a corrected example", "TRF001" in resp, "TRF001")
check("asks to try the step again", "again" in resp, "again")
check("stays on the same step", bad["step_index"] == 0, str(bad["step_index"]))

check(
    "verdict is reduced to outcome + problems",
    sorted(bad["verdict"].keys()) == ["passed", "problems", "status"],
    str(sorted(bad["verdict"].keys())),
)
check(
    "verdict carries no constraints/guidance",
    "constraints" not in bad["verdict"] and "guidance" not in bad["verdict"],
    "absent",
)

print()
print("=" * 72)
print("STEP 3 — valid input: confirm + next step")
print("=" * 72)

good = rr.process_guided_input(db, session_id=sid, user_input="TRF042", user_id=user.id)
scan(good, "valid submission")

resp = good["ai_response"]
check("confirms the step", "Tariff Code accepted" in resp, "Tariff Code accepted")
check("announces the next step", "Step 2 of 2" in resp, "Step 2 of 2")
check("says what to provide next", "Enter the Unit Rate" in resp, "Enter the Unit Rate")
check("shows the next example", "120.00" in resp, "120.00")
check(
    "next example is its own, not the previous step's",
    "TRF001" not in resp.split("Step 2 of 2")[-1],
    "no TRF001 after the step-2 heading",
)

print()
print("=" * 72)
print("STEP 4 — final step completes the walkthrough")
print("=" * 72)

done = rr.process_guided_input(db, session_id=sid, user_input="99.50", user_id=user.id)
scan(done, "final submission")

check("reports completion", done["all_completed"] is True, str(done["all_completed"]))
check(
    "final message confirms all steps",
    "All 2 steps completed" in done["ai_response"],
    "All 2 steps completed",
)

print()
print("=" * 72)
print("Session fetch + unmatched routing stay clean")
print("=" * 72)

scan(rr.get_guided_session(db, session_id=sid, user_id=user.id), "get_guided_session")

routed = rr.route_user_message(
    db, run_id=run.id, user_message="zzzz nothing matches this at all"
)
blob = scan(routed, "route_user_message (unmatched)")
check(
    "listing shows step names only",
    "Tariff Code" in routed["ai_response"] and "SENTINEL_TASK" not in blob,
    "names only",
)

print()
print("=" * 72)
print("step_by_step_service messages")
print("=" * 72)

from app.services import step_by_step_service as sbs

from app.services import step_presenter as _p

fail_msg = sbs._render_blocks(
    _p.build_failure_message(
        {"rule_name": RULES[0]["name"], "suggested_example": "TRF001"},
        0,
        2,
        {"validation_errors": ["Value must start with 'TRF'."]},
        corrected_example="TRF001",
    )
)
scan({"m": fail_msg}, "sbs failure response")
check("sbs failure names the problem", "must start with" in fail_msg, "ok")
check("sbs failure offers correction", "TRF001" in fail_msg, "TRF001")
check(
    "sbs failure no longer prints 'Requirement:'",
    "Requirement:" not in fail_msg,
    "absent",
)

ok_msg = sbs._render_blocks(
    _p.build_success_message(
        {"rule_name": RULES[0]["name"]},
        0,
        2,
        next_step={
            "rule_name": RULES[1]["name"],
            "suggested_example": RULES[1]["example_input"],
        },
    )
)
scan({"m": ok_msg}, "sbs success response")
check("sbs success announces next step", "Unit Rate" in ok_msg, "Unit Rate")

print()
print("=" * 72)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 72)
sys.exit(1 if FAIL else 0)
