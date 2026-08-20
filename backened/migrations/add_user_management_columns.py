"""
Migration: add role, access, address and last_login_at to users.

create_all() only creates missing tables — it never adds a column to
one that already exists — so this has to run once after deploying the
model change.

Existing users are backfilled to role='admin', which preserves their
current effective access: before this column existed, everyone using
the app had unrestricted access, so the migration does not silently
lock anyone out of a page they could previously reach. New
self-registrations (via /auth/register) default to 'member' at the
Python/ORM level — see the comment on User.role in app/db/models.py.

Safe to run more than once: each column is only added if missing.

Usage:
    python migrations/add_user_management_columns.py
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

TABLE_NAME = "users"


def column_exists(session, table_name: str, column_name: str) -> bool:
    result = session.execute(text("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = :table_name
          AND COLUMN_NAME = :column_name
    """), {"table_name": table_name, "column_name": column_name})
    return result.scalar() > 0


def add_column(session, column_name: str, ddl: str) -> None:
    if column_exists(session, TABLE_NAME, column_name):
        print(f"Column already exists: {TABLE_NAME}.{column_name}")
        return

    session.execute(text(f"ALTER TABLE {TABLE_NAME} ADD {ddl}"))
    session.commit()
    print(f"Added {TABLE_NAME}.{column_name}")


def migrate():
    session = SessionLocal()
    try:
        add_column(
            session, "role",
            "role NVARCHAR(20) NOT NULL "
            "CONSTRAINT DF_users_role DEFAULT 'admin'",
        )
        add_column(session, "access", "access NVARCHAR(MAX) NULL")
        add_column(session, "address", "address NVARCHAR(255) NULL")
        add_column(session, "last_login_at", "last_login_at DATETIMEOFFSET NULL")

        admins = session.execute(text(f"""
            SELECT COUNT(*) FROM {TABLE_NAME} WHERE role = 'admin'
        """)).scalar()

        print(f"\n{admins} existing user(s) are now administrators.")
        print("Migration completed successfully.")

    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate()
