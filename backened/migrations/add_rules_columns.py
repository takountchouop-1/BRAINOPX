"""
Migration: add rules_content and related columns to configuration_tasks.

Run this once against your SQL Server database after deploying the model changes.

Usage:
    python migrations/add_rules_columns.py
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

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
import urllib.parse
params = urllib.parse.quote_plus(odbc_str)
SQLALCHEMY_DATABASE_URL = f"mssql+pyodbc:///?odbc_connect={params}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


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
        table_name = "configuration_tasks"
        columns_to_add = {
            "rules_document_filename": "NVARCHAR(255) NULL",
            "rules_document_path": "NVARCHAR(500) NULL",
            "rules_content": "NVARCHAR(MAX) NULL",
        }

        for column_name, column_type in columns_to_add.items():
            if not column_exists(session, table_name, column_name):
                session.execute(text(
                    f"ALTER TABLE {table_name} ADD {column_name} {column_type}"
                ))
                print(f"Added column: {column_name}")
            else:
                print(f"Column already exists: {column_name}")

        session.commit()
        print("Migration completed successfully.")
    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    migrate()
