"""
User management: admin gating, creation with a generated password,
role/access updates, and the self-lockout guards.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.db.database import Base
from app.db.models import User
from app.db.deps import get_current_admin_user
from app.core.security import hash_password, verify_password
from app.schemas.user import UserCreateByAdmin, UserAdminUpdate
from app.routers import users as users_router
from app.routers.users import list_users, create_user, update_user_access
from app.services import user_access

# Never let a test hit real SMTP — creating a user must not send a
# real email to whatever address a test happens to use. Track calls
# instead, and let a later test drive the "SMTP unreachable" path.
_sent_emails = []


def _fake_send_email(to_email, full_name, temporary_password):
    _sent_emails.append((to_email, full_name, temporary_password))


users_router.send_new_user_email = _fake_send_email

FAIL = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + ("  -> " + detail if detail else ""))
    if not cond:
        FAIL.append(label)


engine = create_engine("sqlite://")
Base.metadata.create_all(bind=engine)
db = sessionmaker(bind=engine)()

admin = User(full_name="Admin One", email="admin@x.com", hashed_password=hash_password("x"), role="admin")
member = User(full_name="Regular Member", email="member@x.com", hashed_password=hash_password("x"), role="member")
db.add_all([admin, member])
db.commit()

print("=" * 74)
print("Access tag parsing survives whatever is actually stored")
print("=" * 74)

check("None reads as empty", user_access.parse_access(None) == [], "empty")
check("invalid JSON reads as empty", user_access.parse_access("{not json") == [], "empty")
check("a non-list JSON value reads as empty", user_access.parse_access('"oops"') == [], "empty")
check("unknown tags are dropped", user_access.parse_access('["data_export","made_up"]') == ["data_export"], "filtered")
check("encode then parse round-trips", user_access.parse_access(user_access.encode_access(["data_import", "data_export"])) == ["data_import", "data_export"], "round-trip")
check("duplicate tags collapse", user_access.encode_access(["data_export", "data_export"]) == '["data_export"]', "deduped")

print()
print("=" * 74)
print("Only an admin may reach admin-only routes")
print("=" * 74)

check("an admin passes the dependency", get_current_admin_user(current_user=admin).id == admin.id, "passed")
try:
    get_current_admin_user(current_user=member)
    check("a member is refused", False, "no exception raised")
except HTTPException as exc:
    check("a member is refused", exc.status_code == 403, f"HTTP {exc.status_code}")

print()
print("=" * 74)
print("Creating a user")
print("=" * 74)

result = create_user(
    body=UserCreateByAdmin(
        full_name="New Hire",
        email="new.hire@x.com",
        address="12 Rue Bastos, Yaounde",
        role="member",
        access=["data_export"],
    ),
    db=db,
    current_user=admin,
)

created = result["user"]
temp_password = result["temporary_password"]

check("the user was created", created.email == "new.hire@x.com", created.email)
check("a temporary password was returned", bool(temp_password) and len(temp_password) >= 10, repr(temp_password))
check("the welcome email was sent (mocked)", result["email_sent"] is True, str(result["email_sent"]))
check("the mocked email got the right password",
      _sent_emails and _sent_emails[-1][2] == temp_password,
      str(_sent_emails[-1] if _sent_emails else "none sent"))

# A real SMTP failure must not block account creation — the admin
# still has the password from the response.
def _broken_send_email(*args, **kwargs):
    raise ConnectionError("smtp unreachable")


users_router.send_new_user_email = _broken_send_email

result_broken = create_user(
    body=UserCreateByAdmin(full_name="No Mail", email="no.mail@x.com"),
    db=db, current_user=admin,
)
check("account creation survives an SMTP failure",
      result_broken["user"].email == "no.mail@x.com", "created anyway")
check("the failure is reported rather than hidden",
      result_broken["email_sent"] is False, str(result_broken["email_sent"]))
check("the password is still returned so the admin can hand it over",
      bool(result_broken["temporary_password"]), "present")

users_router.send_new_user_email = _fake_send_email

stored = db.query(User).filter_by(email="new.hire@x.com").first()
check("the password actually works for login",
      verify_password(temp_password, stored.hashed_password), "verified")
check("the address was saved", stored.address == "12 Rue Bastos, Yaounde", stored.address)
check("the role was saved", stored.role == "member", stored.role)
check("access tags were saved", user_access.parse_access(stored.access) == ["data_export"], stored.access)

try:
    create_user(
        body=UserCreateByAdmin(full_name="Dupe", email="new.hire@x.com"),
        db=db, current_user=admin,
    )
    check("a duplicate email is refused", False, "no exception raised")
except HTTPException as exc:
    check("a duplicate email is refused", exc.status_code == 400, f"HTTP {exc.status_code}")

# An invalid role is not silently accepted — it falls back to member.
result2 = create_user(
    body=UserCreateByAdmin(full_name="Odd Role", email="odd@x.com", role="superuser"),
    db=db, current_user=admin,
)
check("an unrecognised role falls back to member",
      result2["user"].role == "member", result2["user"].role)

print()
print("=" * 74)
print("Display tags — what the table shows")
print("=" * 74)

check("an admin with no extra tags shows just Admin",
      user_access.display_tags("admin", []) == ["Admin"], "Admin only")
check("a member with both tags shows both, in order",
      user_access.display_tags("member", ["data_import", "data_export"]) == ["Data Export", "Data Import"],
      str(user_access.display_tags("member", ["data_import", "data_export"])))
check("a member with nothing shows nothing",
      user_access.display_tags("member", []) == [], "empty")

print()
print("=" * 74)
print("Changing an existing user's access")
print("=" * 74)

updated = update_user_access(
    user_id=stored.id,
    body=UserAdminUpdate(role="admin", access=["data_export", "data_import"]),
    db=db, current_user=admin,
)
check("role changed", updated.role == "admin", updated.role)
check("access changed", updated.access == ["data_export", "data_import"], str(updated.access))

deactivated = update_user_access(
    user_id=stored.id,
    body=UserAdminUpdate(is_active=False),
    db=db, current_user=admin,
)
check("the account was deactivated", deactivated.is_active is False, str(deactivated.is_active))

try:
    update_user_access(user_id=999999, body=UserAdminUpdate(role="admin"), db=db, current_user=admin)
    check("a missing user 404s", False, "no exception raised")
except HTTPException as exc:
    check("a missing user 404s", exc.status_code == 404, f"HTTP {exc.status_code}")

try:
    update_user_access(user_id=stored.id, body=UserAdminUpdate(role="not_a_role"), db=db, current_user=admin)
    check("an invalid role is refused", False, "no exception raised")
except HTTPException as exc:
    check("an invalid role is refused", exc.status_code == 400, f"HTTP {exc.status_code}")

print()
print("=" * 74)
print("An admin cannot lock themselves out")
print("=" * 74)

try:
    update_user_access(user_id=admin.id, body=UserAdminUpdate(role="member"), db=db, current_user=admin)
    check("cannot demote self", False, "no exception raised")
except HTTPException as exc:
    check("cannot demote self", exc.status_code == 400, f"HTTP {exc.status_code}")

try:
    update_user_access(user_id=admin.id, body=UserAdminUpdate(is_active=False), db=db, current_user=admin)
    check("cannot deactivate self", False, "no exception raised")
except HTTPException as exc:
    check("cannot deactivate self", exc.status_code == 400, f"HTTP {exc.status_code}")

# But an admin CAN still demote or deactivate someone else.
update_user_access(user_id=member.id, body=UserAdminUpdate(is_active=False), db=db, current_user=admin)
db.refresh(member)
check("an admin can deactivate another account", member.is_active is False, "deactivated")

print()
print("=" * 74)
print("The list endpoint")
print("=" * 74)

payload = list_users(db=db, current_user=admin)
check("every created user is listed", payload["summary"]["total"] == db.query(User).count(),
      str(payload["summary"]))
check("admins are counted", payload["summary"]["admins"] >= 2, str(payload["summary"]["admins"]))

print()
print("=" * 74)
print("A member can view the roster but not manage it")
print("=" * 74)

check("a member CAN list users (viewing is not restricted)",
      list_users(db=db, current_user=member)["summary"]["total"] > 0, "viewable")

# create_user / update_user_access enforce their admin requirement
# through FastAPI's dependency injection — Depends(get_current_admin_user)
# only runs inside the real request pipeline. Calling the endpoint
# function directly with current_user=member (as above) bypasses that
# pipeline entirely and would give a false pass. What is actually
# checked at request time is which dependency the route is wired to,
# so that is what is asserted here — same technique used for
# create_task below.
import inspect as _inspect
from app.db.deps import get_current_admin_user as _admin_dep

def _current_user_dependency(fn):
    return _inspect.signature(fn).parameters["current_user"].default.dependency

check("creating a user requires an admin (enforced by FastAPI's DI, not by the function body)",
      _current_user_dependency(create_user) is _admin_dep, "admin-gated")
check("changing a user's access requires an admin",
      _current_user_dependency(update_user_access) is _admin_dep, "admin-gated")

print()
print("=" * 74)
print("A member cannot create a task, but everyone else can still act on tasks")
print("=" * 74)

import inspect

from app.routers.tasks import create_task, list_tasks, update_task, delete_task
from app.db.deps import get_current_admin_user, get_current_user

# create_task takes multipart form fields and file uploads, which is
# awkward to call directly in a unit test; what matters here is the
# authorization boundary, so assert on the dependency FastAPI will
# actually enforce rather than exercising the whole endpoint.
def _depends_on(fn, param="current_user"):
    return inspect.signature(fn).parameters[param].default.dependency


check("creating a task requires an admin",
      _depends_on(create_task) is get_current_admin_user, "admin-gated")
check("listing tasks stays open to any signed-in user",
      _depends_on(list_tasks) is get_current_user, "view open")
check("editing an existing task stays open (only creation is restricted)",
      _depends_on(update_task) is get_current_user, "unrestricted")
check("deleting a task stays open (only creation is restricted)",
      _depends_on(delete_task) is get_current_user, "unrestricted")

print()
print("=" * 74)
print("Deleting a user")
print("=" * 74)

from app.routers.users import delete_user
from app.db.models import ConfigurationRequest, ConfigurationTask, Notification, SkillEngineRun

check("delete_user requires an admin",
      _current_user_dependency(delete_user) is _admin_dep, "admin-gated")

try:
    delete_user(user_id=admin.id, db=db, current_user=admin)
    check("an admin cannot delete themselves", False, "no exception raised")
except HTTPException as exc:
    check("an admin cannot delete themselves", exc.status_code == 400, f"HTTP {exc.status_code}")

try:
    delete_user(user_id=999999, db=db, current_user=admin)
    check("deleting a missing user 404s", False, "no exception raised")
except HTTPException as exc:
    check("deleting a missing user 404s", exc.status_code == 404, f"HTTP {exc.status_code}")

# A user with real history is refused, not silently cascaded or
# left to hit a raw FK constraint error.
task = ConfigurationTask(
    name="T", category="skill_engine", template_filename="t",
    template_file_path="t", expected_columns="[]",
)
db.add(task)
db.commit()

busy = User(full_name="Busy Person", email="busy@x.com", hashed_password=hash_password("x"), role="member")
db.add(busy)
db.commit()

run = SkillEngineRun(user_id=busy.id, status="completed", rules_json="[]")
db.add(run)
db.commit()

try:
    delete_user(user_id=busy.id, db=db, current_user=admin)
    check("a user with a run cannot be hard-deleted", False, "no exception raised")
except HTTPException as exc:
    check("a user with a run cannot be hard-deleted", exc.status_code == 400, f"HTTP {exc.status_code}")
    check("the refusal names what is blocking it and suggests deactivating",
          "skill-engine run" in exc.detail and "Deactivate" in exc.detail, exc.detail)

check("the blocked user still exists",
      db.query(User).filter_by(id=busy.id).first() is not None, "kept")

# A clean account — no history anywhere — can be hard-deleted.
clean = User(full_name="Clean Slate", email="clean@x.com", hashed_password=hash_password("x"), role="member")
db.add(clean)
db.commit()
clean_id = clean.id

note = Notification(user_id=clean.id, title="hi", type="info")
db.add(note)
db.commit()

authored = ConfigurationTask(
    name="Authored by clean", category="skill_engine", template_filename="t",
    template_file_path="t", expected_columns="[]", created_by=clean.id,
)
db.add(authored)
db.commit()
authored_id = authored.id

result = delete_user(user_id=clean_id, db=db, current_user=admin)
check("a clean account is deleted", result == {"deleted": True, "id": clean_id}, str(result))
check("the row is gone",
      db.query(User).filter_by(id=clean_id).first() is None, "removed")
check("their notifications went with them",
      db.query(Notification).filter_by(user_id=clean_id).count() == 0, "removed")

db.refresh(authored)
check("a task they authored survives, unassigned rather than destroyed",
      db.query(ConfigurationTask).filter_by(id=authored_id).first() is not None
      and authored.created_by is None,
      f"created_by={authored.created_by}")

print()
print("=" * 74)
print("RESULT:", "ALL PASSED" if not FAIL else f"{len(FAIL)} FAILED -> {FAIL}")
print("=" * 74)
sys.exit(1 if FAIL else 0)
