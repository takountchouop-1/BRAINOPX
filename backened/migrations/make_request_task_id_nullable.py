"""
Migration: make configuration_requests.task_id nullable.

An upload whose Excel file doesn't match any task template now opens a
configuration request with no task attached (task_id NULL) so the AI
assistant can ask for more information and, if asked, escalate to an
expert instead of leaving the user at a dead end. The SQLAlchemy model
was changed to nullable=True; this migration applies the same change to
an existing SQL Server database, since create_all() never alters a
column that already exists.

Safe to run more than once: it only alters the column if it is still
NOT NULL.

Usage:
    python migrations/make_request_task_id_nullable.py
"""
import os
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

TABLE_NAME = "configuration_requests"
COLUMN_NAME = "task_id"


def is_nullable(session, table_name: str, column_name: str) -> bool:
    result = session.execute(text("""
        SELECT IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = :table_name
          AND COLUMN_NAME = :column_name
    """), {"table_name": table_name, "column_name": column_name})
    value = result.scalar()
    return (value or "").strip().upper() == "YES"


def migrate():
    session = SessionLocal()
    try:
        if is_nullable(session, TABLE_NAME, COLUMN_NAME):
            print(f"{TABLE_NAME}.{COLUMN_NAME} is already nullable.")
            return

        session.execute(text(
            f"ALTER TABLE {TABLE_NAME} ALTER COLUMN {COLUMN_NAME} INT NULL"
        ))
        session.commit()
        print(f"Made {TABLE_NAME}.{COLUMN_NAME} nullable.")
        print("Migration completed successfully.")

    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate()
