"""
The dashboard endpoint's progress and bucket logic.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routers.requests import _request_progress

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


class FakeRequest:
    def __init__(self, eval_profile=None, validation_errors=None, status="draft"):
        self.eval_profile = eval_profile
        self.validation_errors = validation_errors
        self.status = status


print("=" * 72)
print("Progress from the step-by-step walkthrough")
print("=" * 72)

workflow = json.dumps({
    "step_workflow": {"total_steps": 8, "completed_steps": 2, "current_step": 2}
})
p = _request_progress(FakeRequest(eval_profile=workflow))
check("2 of 8 steps is 25%", p == {"completed_steps": 2, "total_steps": 8, "percent": 25}, str(p))

full = json.dumps({"step_workflow": {"total_steps": 8, "completed_steps": 8}})
check("all steps is 100%",
      _request_progress(FakeRequest(eval_profile=full))["percent"] == 100, "100")

# A workflow that over-counts must not exceed the total.
over = json.dumps({"step_workflow": {"total_steps": 5, "completed_steps": 9}})
p = _request_progress(FakeRequest(eval_profile=over))
check("an over-count is capped", p["completed_steps"] == 5 and p["percent"] == 100, str(p))

print()
print("=" * 72)
print("Falling back to validation errors")
print("=" * 72)

errors = json.dumps([
    {"column": "a", "solved": True},
    {"column": "b", "solved": False},
    {"column": "c", "solved": True},
    {"column": "d", "solved": False},
])
p = _request_progress(FakeRequest(validation_errors=errors))
check("2 of 4 errors resolved is 50%", p["percent"] == 50, str(p))

print()
print("=" * 72)
print("Falling back to status")
print("=" * 72)

for status, expected in [
    ("draft", 0),
    ("analysis_in_progress", 0),
    ("data_validated", 100),
    ("script_generated", 100),
    ("processing_completed", 100),
]:
    got = _request_progress(FakeRequest(status=status))["percent"]
    check(f"{status!r} -> {expected}%", got == expected, str(got))

print()
print("=" * 72)
print("Broken stored data is survivable")
print("=" * 72)

check("invalid eval_profile JSON",
      _request_progress(FakeRequest(eval_profile="{not json"))["percent"] == 0, "recovered")
check("invalid validation_errors JSON",
      _request_progress(FakeRequest(validation_errors="[oops"))["percent"] == 0, "recovered")
check("eval_profile without a workflow",
      _request_progress(FakeRequest(eval_profile='{"other": 1}'))["percent"] == 0, "recovered")
check("a zero-step workflow does not divide by zero",
      _request_progress(
          FakeRequest(eval_profile='{"step_workflow": {"total_steps": 0}}')
      )["percent"] == 0,
      "recovered")
check("an empty error list does not divide by zero",
      _request_progress(FakeRequest(validation_errors="[]"))["percent"] == 0, "recovered")

print()
print("=" * 72)
print("The dashboard query is valid on SQL Server, and runs end to end")
print("=" * 72)

from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import ConfigurationRequest, ConfigurationTask, User
from app.routers.requests import list_requests

# The ordering must compile to T-SQL. NULLS LAST is valid in SQLite
# and PostgreSQL but not SQL Server, so compiling against SQLite
# alone would not have caught it.
ordering = select(ConfigurationRequest.id).order_by(
    func.coalesce(
        ConfigurationRequest.updated_at,
        ConfigurationRequest.created_at,
    ).desc(),
    ConfigurationRequest.id.desc(),
)
tsql = str(ordering.compile(dialect=mssql.dialect())).upper()

check("the ordering compiles for SQL Server", "ORDER BY" in tsql, "compiled")
check("it does not use NULLS LAST", "NULLS" not in tsql, "portable")

# And the endpoint itself returns what the dashboard expects.
engine = create_engine("sqlite://")
Base.metadata.create_all(bind=engine)
db = sessionmaker(bind=engine)()

owner = User(full_name="Kengne Christ", email="k@x.com", hashed_password="x")
db.add(owner)
db.commit()

task = ConfigurationTask(
    name="Tariff Setup", category="skill_engine",
    template_filename="t", template_file_path="t", expected_columns="[]",
)
db.add(task)
db.commit()

db.add_all([
    ConfigurationRequest(
        task_id=task.id, user_id=owner.id, status="draft",
    ),
    ConfigurationRequest(
        task_id=task.id, user_id=owner.id, status="analysis_in_progress",
        eval_profile=json.dumps(
            {"step_workflow": {"total_steps": 8, "completed_steps": 4}}
        ),
    ),
    ConfigurationRequest(
        task_id=task.id, user_id=owner.id, status="processing_completed",
    ),
    # task_id and user_id are NOT NULL, so the only way a row can
    # lose its task or owner is a dangling reference — a deleted
    # user, say. Both outer joins must survive that.
    ConfigurationRequest(task_id=9999, user_id=9999, status="draft"),
])
db.commit()

payload = list_requests(db=db, current_user=owner)

summary = payload["summary"]
items = payload["items"]

check("every request is returned", len(items) == 4, str(len(items)))
check("totals add up",
      summary["completed"] + summary["pending"] + summary["not_started"] == summary["total"],
      str(summary))
check("completed counted", summary["completed"] == 1, str(summary["completed"]))
check("in progress counted", summary["pending"] == 1, str(summary["pending"]))
check("not started counted", summary["not_started"] == 2, str(summary["not_started"]))
check("overall progress averaged", summary["overall_progress"] == 38,
      str(summary["overall_progress"]))

with_owner = [i for i in items if i["owner"]]
check("the owner travels with the row",
      with_owner and with_owner[0]["owner"]["full_name"] == "Kengne Christ",
      str(with_owner[0]["owner"]) if with_owner else "none")
check("a request with no task still returns",
      any(i["task_name"] == "Unassigned task" for i in items), "handled")
check("a request with no owner still returns",
      any(i["owner"] is None for i in items), "handled")
check("the half-done request reports 50%",
      any(i["progress"] == 50 for i in items),
      str([i["progress"] for i in items]))

print()
print("=" * 72)
print("Deleting a request")
print("=" * 72)

import os as _os
import tempfile as _tempfile

from fastapi import HTTPException

from app.routers import requests as requests_router
from app.routers.requests import delete_request

other = User(full_name="Someone Else", email="other@x.com", hashed_password="x")
db.add(other)
db.commit()

# A request with a real uploaded file inside the upload directory.
upload_root = _tempfile.mkdtemp()
requests_router.UPLOAD_DIR = upload_root

uploaded = _os.path.join(upload_root, "sheet.xlsx")
with open(uploaded, "w", encoding="utf-8") as fh:
    fh.write("data")

owned = ConfigurationRequest(
    task_id=task.id, user_id=owner.id, status="draft",
    uploaded_filename="sheet.xlsx", uploaded_file_path=uploaded,
)
db.add(owned)
db.commit()
owned_id = owned.id

# Another person's request must be refused.
try:
    delete_request(request_id=owned_id, db=db, current_user=other)
    check("another user cannot delete it", False, "no exception raised")
except HTTPException as exc:
    check("another user cannot delete it", exc.status_code == 403, f"HTTP {exc.status_code}")

check("the refused request still exists",
      db.query(ConfigurationRequest).filter_by(id=owned_id).first() is not None,
      "kept")
check("its file was not touched", _os.path.isfile(uploaded), "kept")

# The owner can.
result = delete_request(request_id=owned_id, db=db, current_user=owner)
check("the owner can delete it", result.get("deleted") is True, str(result))
check("the row is gone",
      db.query(ConfigurationRequest).filter_by(id=owned_id).first() is None, "removed")
check("the uploaded file is gone", not _os.path.isfile(uploaded), "removed")
check("the task template is kept",
      db.query(ConfigurationTask).filter_by(id=task.id).first() is not None,
      "reusable")

# A request that no longer exists.
try:
    delete_request(request_id=owned_id, db=db, current_user=owner)
    check("deleting a missing request 404s", False, "no exception raised")
except HTTPException as exc:
    check("deleting a missing request 404s", exc.status_code == 404, f"HTTP {exc.status_code}")

print()
print("=" * 72)
print("A stored path outside the upload directory is never followed")
print("=" * 72)

outside = _os.path.join(_tempfile.mkdtemp(), "important.txt")
with open(outside, "w", encoding="utf-8") as fh:
    fh.write("do not delete me")

stray = ConfigurationRequest(
    task_id=task.id, user_id=owner.id, status="draft",
    uploaded_filename="important.txt", uploaded_file_path=outside,
)
db.add(stray)
db.commit()

delete_request(request_id=stray.id, db=db, current_user=owner)

check("the record is still deleted",
      db.query(ConfigurationRequest).filter_by(id=stray.id).first() is None, "removed")
check("the file outside the upload directory survives",
      _os.path.isfile(outside), "untouched")

# A missing file must not stop the record going.
ghost = ConfigurationRequest(
    task_id=task.id, user_id=owner.id, status="draft",
    uploaded_file_path=_os.path.join(upload_root, "gone.xlsx"),
)
db.add(ghost)
db.commit()

delete_request(request_id=ghost.id, db=db, current_user=owner)
check("a missing file does not block deletion",
      db.query(ConfigurationRequest).filter_by(id=ghost.id).first() is None, "removed")

print()
print("=" * 72)
print("Deleting several at once")
print("=" * 72)

from app.routers.requests import bulk_delete_requests, BulkDeleteBody

mine = []
for _ in range(3):
    r = ConfigurationRequest(task_id=task.id, user_id=owner.id, status="draft")
    db.add(r)
    mine.append(r)

theirs = ConfigurationRequest(task_id=task.id, user_id=other.id, status="draft")
db.add(theirs)
db.commit()

my_ids = [r.id for r in mine]
their_id = theirs.id

# A batch mixing my rows, someone else's, and one that never existed.
result = bulk_delete_requests(
    body=BulkDeleteBody(ids=my_ids + [their_id, 999999]),
    db=db,
    current_user=owner,
)

check("my requests were deleted", sorted(result["deleted"]) == sorted(my_ids), str(result["deleted"]))
check("the count matches", result["deleted_count"] == 3, str(result["deleted_count"]))
check("someone else's was refused", result["forbidden"] == [their_id], str(result["forbidden"]))
check("a missing id is reported", result["missing"] == [999999], str(result["missing"]))

check("my rows are gone",
      db.query(ConfigurationRequest).filter(ConfigurationRequest.id.in_(my_ids)).count() == 0,
      "removed")
check("the refused row survives",
      db.query(ConfigurationRequest).filter_by(id=their_id).first() is not None,
      "kept")

# One bad id must not take the batch down with it.
keep = ConfigurationRequest(task_id=task.id, user_id=owner.id, status="draft")
db.add(keep)
db.commit()

result = bulk_delete_requests(
    body=BulkDeleteBody(ids=[keep.id, their_id]),
    db=db,
    current_user=owner,
)
check("a partial batch still deletes what it can",
      result["deleted_count"] == 1 and result["forbidden"] == [their_id],
      str(result))

# Duplicates in the selection must not double-count.
dupe = ConfigurationRequest(task_id=task.id, user_id=owner.id, status="draft")
db.add(dupe)
db.commit()

result = bulk_delete_requests(
    body=BulkDeleteBody(ids=[dupe.id, dupe.id, dupe.id]),
    db=db,
    current_user=owner,
)
check("duplicate ids are counted once", result["deleted_count"] == 1, str(result))

# An empty selection is a bad request, not a silent no-op.
try:
    bulk_delete_requests(body=BulkDeleteBody(ids=[]), db=db, current_user=owner)
    check("an empty selection is rejected", False, "no exception raised")
except HTTPException as exc:
    check("an empty selection is rejected", exc.status_code == 400, f"HTTP {exc.status_code}")

print()
print("=" * 72)
print("Priority")
print("=" * 72)

from app.routers.requests import set_request_priority, PriorityBody

target = ConfigurationRequest(task_id=task.id, user_id=owner.id, status="draft")
db.add(target)
db.commit()

check("a new request defaults to medium", target.priority == "medium", str(target.priority))

result = set_request_priority(
    request_id=target.id, body=PriorityBody(priority="high"),
    db=db, current_user=owner,
)
check("the owner can raise it", result["priority"] == "high", str(result))
db.refresh(target)
check("it is persisted", target.priority == "high", str(target.priority))

# Case and whitespace should not matter.
set_request_priority(
    request_id=target.id, body=PriorityBody(priority="  LOW  "),
    db=db, current_user=owner,
)
db.refresh(target)
check("input is normalised", target.priority == "low", str(target.priority))

# Anything outside the three values is refused.
for bad in ("urgent", "", "critical", "1"):
    try:
        set_request_priority(
            request_id=target.id, body=PriorityBody(priority=bad),
            db=db, current_user=owner,
        )
        check(f"{bad!r} refused", False, "no exception raised")
    except HTTPException as exc:
        check(f"{bad!r} refused", exc.status_code == 400, f"HTTP {exc.status_code}")

db.refresh(target)
check("a refused value leaves it unchanged", target.priority == "low", str(target.priority))

# Someone else's request.
try:
    set_request_priority(
        request_id=target.id, body=PriorityBody(priority="high"),
        db=db, current_user=other,
    )
    check("another user cannot change it", False, "no exception raised")
except HTTPException as exc:
    check("another user cannot change it", exc.status_code == 403, f"HTTP {exc.status_code}")

try:
    set_request_priority(
        request_id=999999, body=PriorityBody(priority="high"),
        db=db, current_user=owner,
    )
    check("a missing request 404s", False, "no exception raised")
except HTTPException as exc:
    check("a missing request 404s", exc.status_code == 404, f"HTTP {exc.status_code}")

# And it travels on the dashboard payload.
payload = list_requests(db=db, current_user=owner)
row = next((i for i in payload["items"] if i["id"] == target.id), None)
check("priority is returned by the list endpoint",
      row is not None and row["priority"] == "low",
      str(row and row["priority"]))
check("every row carries a priority",
      all(i.get("priority") in ("low", "medium", "high") for i in payload["items"]),
      str(sorted({i.get("priority") for i in payload["items"]})))

print()
print("=" * 72)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 72)
sys.exit(1 if FAIL else 0)
