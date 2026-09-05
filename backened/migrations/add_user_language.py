"""
Migration: add the language column to users.

create_all() only creates missing tables — it never adds a column to
a table that already exists — so this has to run once against the
database after deploying the model change.

Existing rows are backfilled to "en" by the column default, so
nothing comes back NULL.

Safe to run more than once: the column is only added if missing.

Usage:
    python migrations/add_user_language.py
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
COLUMN_NAME = "language"


def column_exists(session, table_name: str, column_name: str) -> bool:
    result = session.execute(text("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = :table_name
          AND COLUMN_NAME = :column_name
    """), {"table_name": table_name, "column_name": column_name})
    return result.scalar() > 0


def migrate():
    session = SessionLocal()
    try:
        if column_exists(session, TABLE_NAME, COLUMN_NAME):
            print(f"Column already exists: {TABLE_NAME}.{COLUMN_NAME}")
            return

        # NOT NULL with a DEFAULT so existing rows are filled in as
        # part of the same statement.
        session.execute(text(f"""
            ALTER TABLE {TABLE_NAME}
            ADD {COLUMN_NAME} NVARCHAR(5) NOT NULL
            CONSTRAINT DF_users_language DEFAULT 'en'
        """))
        session.commit()

        filled = session.execute(text(f"""
            SELECT COUNT(*) FROM {TABLE_NAME} WHERE {COLUMN_NAME} = 'en'
        """)).scalar()

        print(f"Added {TABLE_NAME}.{COLUMN_NAME}")
        print(f"{filled} existing user(s) set to 'en'.")
        print("Migration completed successfully.")

    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate()
