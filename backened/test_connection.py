"""
Standalone script to verify connectivity to SQL Server.
Run this from inside your activated venv:
    python test_connection.py
"""

import os
import pyodbc
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME = os.getenv("DB_NAME")
DB_DRIVER = os.getenv("DB_DRIVER")
DB_TRUSTED_CONNECTION = os.getenv("DB_TRUSTED_CONNECTION", "yes")

def build_connection_string():
    return (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        f"Trusted_Connection={DB_TRUSTED_CONNECTION};"
        f"TrustServerCertificate=yes;"
    )

def test_connection():
    conn_str = build_connection_string()
    print("Attempting connection with:")
    print(conn_str.replace(DB_SERVER, "****"))  # avoid printing sensitive server info directly

    try:
        conn = pyodbc.connect(conn_str, timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS test_value;")
        row = cursor.fetchone()
        print(f"\n Connection successful. Test query returned: {row.test_value}")

        cursor.execute("SELECT DB_NAME() AS current_db;")
        row = cursor.fetchone()
        print(f" Connected to database: {row.current_db}")

        conn.close()
    except pyodbc.Error as e:
        print("\n Connection failed.")
        print(f"Error details: {e}")

if __name__ == "__main__":
    test_connection()
