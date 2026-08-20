import json
import os
import sys

sys.path.insert(0, r"e:\BRAINOPX\backened")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import User, SkillEngineRun, GuidedSession
from app.services import rule_router_service as rr
from fastapi import HTTPException

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


engine = create_engine("sqlite://")
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
db = Session()

# Count SELECTs against skill_engine_runs, to prove the scan is gone.
scan_counter = {"n": 0}


@event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, params, context, executemany):
    s = " ".join(statement.split()).lower()
    if s.startswith("select") and "from skill_engine_runs" in s:
        scan_counter["n"] += 1


owner = User(full_name="Owner", email="owner@x.com", hashed_password="x")
other = User(full_name="Other", email="other@x.com", hashed_password="x")
db.add_all([owner, other])
db.commit()

RULES = [
    {
        "id": 1,
        "name": "Tariff Code",
        "description": "Must start with TRF followed by 3 digits",
        "example_input": "TRF001",
    },
    {
        "id": 2,
        "name": "Unit Rate",
        "description": "Must be a positive number",
        "example_input": "120.00",
    },
]

ORIGINAL_RESULTS = {"results": [{"rule_id": 1, "status": "passed"}]}

run = SkillEngineRun(
    user_id=owner.id,
    status="completed",
    rules_json=json.dumps(RULES),
    results_json=json.dumps(ORIGINAL_RESULTS),
)
db.add(run)
db.commit()

print("=" * 72)
print("Session creation writes its own row, not the run's results blob")
print("=" * 72)

started = rr.init_guided_session(db, run_id=run.id, user_id=owner.id)
session_id = started["session"]["session_id"]

record = db.query(GuidedSession).filter_by(session_id=session_id).first()
check("guided_sessions row created", record is not None, session_id)
check("row carries run_id", record.run_id == run.id, str(record.run_id))
check("row carries user_id", record.user_id == owner.id, str(record.user_id))
check("row carries step count", record.total_steps == 2, str(record.total_steps))

db.refresh(run)
check(
    "run.results_json left untouched",
    json.loads(run.results_json) == ORIGINAL_RESULTS,
    run.results_json,
)
check(
    "first step example came from its own rule",
    started["session"]["active_rule"]["suggested_example"] == "TRF001",
    started["session"]["active_rule"]["suggested_example"],
)

print()
print("=" * 72)
print("Lookup is a direct indexed hit, not a scan of recent runs")
print("=" * 72)

# 20 newer runs: under the old 10-run window the session would be lost.
for _ in range(20):
    db.add(SkillEngineRun(
        user_id=owner.id,
        status="completed",
        rules_json="[]",
        results_json=None,
    ))
db.commit()

scan_counter["n"] = 0
fetched = rr.get_guided_session(db, session_id=session_id, user_id=owner.id)
check(
    "session still reachable behind 20 newer runs",
    fetched["session"]["session_id"] == session_id,
    session_id,
)
check(
    "no query against skill_engine_runs to find it",
    scan_counter["n"] == 0,
    f"{scan_counter['n']} run queries",
)

print()
print("=" * 72)
print("Ownership is checked on the session itself")
print("=" * 72)

try:
    rr.get_guided_session(db, session_id=session_id, user_id=other.id)
    check("another user is refused", False, "no exception raised")
except HTTPException as exc:
    check("another user is refused", exc.status_code == 404, f"HTTP {exc.status_code}")

try:
    rr.process_guided_input(
        db, session_id=session_id, user_input="TRF001", user_id=other.id
    )
    check("another user cannot submit", False, "no exception raised")
except HTTPException as exc:
    check("another user cannot submit", exc.status_code == 404, f"HTTP {exc.status_code}")

try:
    rr.init_guided_session(db, run_id=run.id, user_id=other.id)
    check("another user cannot start a session on the run", False, "no exception")
except HTTPException as exc:
    check(
        "another user cannot start a session on the run",
        exc.status_code == 404,
        f"HTTP {exc.status_code}",
    )

print()
print("=" * 72)
print("Progress advances on its own row and leaves results_json alone")
print("=" * 72)

bad = rr.process_guided_input(
    db, session_id=session_id, user_input="NOPE", user_id=owner.id
)
check("invalid value rejected", bad["passed"] is False, str(bad["passed"]))
check("stays on step 0", bad["step_index"] == 0, str(bad["step_index"]))
check(
    "failure explains the problem",
    "TRF" in bad["ai_response"],
    bad["verdict"].get("validation_errors", [""])[0][:60],
)
check(
    "failure offers a correct suggestion",
    bad["suggested_example"] == "TRF001",
    bad["suggested_example"],
)

good = rr.process_guided_input(
    db, session_id=session_id, user_input="TRF042", user_id=owner.id
)
check("valid value accepted", good["passed"] is True, str(good["passed"]))

db.expire_all()
record = db.query(GuidedSession).filter_by(session_id=session_id).first()
check("advanced to step 1 on the row", record.current_step_index == 1, str(record.current_step_index))

steps = json.loads(record.steps_json)
check("step 0 marked completed", steps[0]["status"] == "completed", steps[0]["status"])
check("attempts recorded", steps[0]["attempts"] == 2, str(steps[0]["attempts"]))
check(
    "step 1 got its OWN example, not step 0's",
    steps[1]["suggested_example"] == "120.00",
    steps[1]["suggested_example"],
)

run = db.query(SkillEngineRun).filter_by(id=run.id).first()
check(
    "results_json still untouched after 2 submissions",
    json.loads(run.results_json) == ORIGINAL_RESULTS,
    run.results_json,
)

print()
print("=" * 72)
print("Completing the last rule closes the session")
print("=" * 72)

done = rr.process_guided_input(
    db, session_id=session_id, user_input="99.50", user_id=owner.id
)
check("final rule passes", done["passed"] is True, str(done["passed"]))
check("session reports completion", done["all_completed"] is True, str(done["all_completed"]))

db.expire_all()
record = db.query(GuidedSession).filter_by(session_id=session_id).first()
check("all_completed persisted", bool(record.all_completed) is True, str(record.all_completed))
check("completed_at stamped", record.completed_at is not None, str(record.completed_at))

print()
print("=" * 72)
print("Unknown session id")
print("=" * 72)

try:
    rr.get_guided_session(db, session_id="doesnotexist", user_id=owner.id)
    check("unknown session 404s", False, "no exception raised")
except HTTPException as exc:
    check("unknown session 404s", exc.status_code == 404, f"HTTP {exc.status_code}")

print()
print("=" * 72)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 72)
sys.exit(1 if FAIL else 0)
