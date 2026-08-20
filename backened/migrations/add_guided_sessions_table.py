"""
Migration: create the guided_sessions table and backfill it from
SkillEngineRun.results_json.

Guided sessions used to live inside the run's results_json blob, which
meant a session could only be found by scanning a window of the user's
recent runs, and writing step progress rewrote the whole blob. They now
have their own table keyed by an indexed session_id.

This script:

  1. Creates the guided_sessions table if it does not exist.
  2. Copies every session still embedded in results_json into it.
  3. Strips the guided_sessions key out of results_json, leaving the
     per-rule results untouched.

Existing sessions keep their session_id, so links already held by a
client continue to resolve.

Safe to run more than once — sessions already migrated are skipped.

Usage:
    python migrations/add_guided_sessions_table.py
    python migrations/add_guided_sessions_table.py --dry-run
"""
import json
import os
import sys
import urllib.parse

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME = os.getenv("DB_NAME")
DB_DRIVER = os.getenv("DB_DRIVER")
DB_TRUSTED_CONNECTION = os.getenv("DB_TRUSTED_CONNECTION", "yes")

odbc_str = (
    f"DRIVER={{{DB_DRIVER}}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    f"Trusted_Connection={DB_TRUSTED_CONNECTION};"
    f"TrustServerCertificate=yes;"
)
params = urllib.parse.quote_plus(odbc_str)
SQLALCHEMY_DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

DRY_RUN = "--dry-run" in sys.argv


def table_exists(session, table_name: str) -> bool:
    result = session.execute(text("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME = :table_name
    """), {"table_name": table_name})
    return result.scalar() > 0


CREATE_TABLE_SQL = """
CREATE TABLE guided_sessions (
    id                 INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    session_id         NVARCHAR(32)  NOT NULL UNIQUE,
    run_id             INT           NOT NULL,
    user_id            INT           NOT NULL,
    current_step_index INT           NOT NULL CONSTRAINT DF_gs_step   DEFAULT 0,
    total_steps        INT           NOT NULL CONSTRAINT DF_gs_total  DEFAULT 0,
    all_completed      BIT           NOT NULL CONSTRAINT DF_gs_done   DEFAULT 0,
    steps_json         NVARCHAR(MAX) NOT NULL,
    started_at         DATETIMEOFFSET NULL CONSTRAINT DF_gs_started DEFAULT SYSDATETIMEOFFSET(),
    completed_at       DATETIMEOFFSET NULL,
    updated_at         DATETIMEOFFSET NULL CONSTRAINT DF_gs_updated DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT FK_guided_sessions_run
        FOREIGN KEY (run_id) REFERENCES skill_engine_runs(id) ON DELETE CASCADE,
    CONSTRAINT FK_guided_sessions_user
        FOREIGN KEY (user_id) REFERENCES users(id)
)
"""

INDEX_SQL = [
    "CREATE INDEX IX_guided_sessions_session_id ON guided_sessions(session_id)",
    "CREATE INDEX IX_guided_sessions_run_id ON guided_sessions(run_id)",
    "CREATE INDEX IX_guided_sessions_user_id ON guided_sessions(user_id)",
]


def create_table(session) -> None:
    if table_exists(session, "guided_sessions"):
        print("Table already exists: guided_sessions")
        return

    if DRY_RUN:
        print("[dry-run] would create table: guided_sessions")
        return

    session.execute(text(CREATE_TABLE_SQL))
    for stmt in INDEX_SQL:
        session.execute(text(stmt))
    print("Created table: guided_sessions")


def backfill(session) -> tuple[int, int, int]:
    """Copy embedded sessions into the new table. Returns counts."""

    rows = session.execute(text("""
        SELECT id, user_id, results_json
        FROM skill_engine_runs
        WHERE results_json IS NOT NULL
    """)).fetchall()

    migrated = 0
    skipped = 0
    cleaned = 0

    for run_id, user_id, results_json in rows:

        try:
            meta = json.loads(results_json)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

        if not isinstance(meta, dict):
            continue

        sessions = meta.get("guided_sessions")

        if not isinstance(sessions, dict) or not sessions:
            continue

        for session_id, payload in sessions.items():

            if not isinstance(payload, dict):
                continue

            existing = session.execute(text("""
                SELECT COUNT(*) FROM guided_sessions
                WHERE session_id = :session_id
            """), {"session_id": session_id}).scalar()

            if existing:
                skipped += 1
                continue

            steps = payload.get("steps", [])

            if DRY_RUN:
                print(
                    f"[dry-run] would migrate session {session_id} "
                    f"(run {run_id}, {len(steps)} steps)"
                )
                migrated += 1
                continue

            session.execute(text("""
                INSERT INTO guided_sessions (
                    session_id, run_id, user_id,
                    current_step_index, total_steps, all_completed,
                    steps_json, completed_at
                ) VALUES (
                    :session_id, :run_id, :user_id,
                    :current_step_index, :total_steps, :all_completed,
                    :steps_json, :completed_at
                )
            """), {
                "session_id": session_id,
                "run_id": run_id,
                "user_id": user_id,
                "current_step_index": int(
                    payload.get("current_step_index", 0) or 0
                ),
                "total_steps": len(steps),
                "all_completed": 1 if payload.get("all_completed") else 0,
                "steps_json": json.dumps(steps, ensure_ascii=False),
                "completed_at": payload.get("completed_at"),
            })

            migrated += 1

        # Drop the embedded copy; per-rule results are preserved.

        meta.pop("guided_sessions", None)

        if DRY_RUN:
            print(f"[dry-run] would strip guided_sessions from run {run_id}")
        else:
            session.execute(text("""
                UPDATE skill_engine_runs
                SET results_json = :results_json
                WHERE id = :run_id
            """), {
                "results_json": json.dumps(meta, ensure_ascii=False),
                "run_id": run_id,
            })

        cleaned += 1

    return migrated, skipped, cleaned


def migrate():
    session = SessionLocal()
    try:
        if DRY_RUN:
            print("DRY RUN — no changes will be committed.\n")

        create_table(session)

        if DRY_RUN and not table_exists(session, "guided_sessions"):
            print(
                "\n[dry-run] table does not exist yet, so the backfill "
                "cannot be previewed. Re-run without --dry-run."
            )
            session.rollback()
            return

        migrated, skipped, cleaned = backfill(session)

        if DRY_RUN:
            session.rollback()
            print(
                f"\n[dry-run] {migrated} session(s) would migrate, "
                f"{skipped} already present, {cleaned} run(s) would be cleaned."
            )
            return

        session.commit()
        print(
            f"\nMigrated {migrated} session(s), skipped {skipped} already "
            f"present, cleaned {cleaned} run(s)."
        )
        print("Migration completed successfully.")

    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate()
