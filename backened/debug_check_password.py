"""
Debug script: directly checks whether a given plain-text password
matches the hash currently stored for a specific user.

Run from backend/ with venv activated:
    python debug_check_password.py
"""

import os
import pyodbc
import bcrypt
from dotenv import load_dotenv

load_dotenv()

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME = os.getenv("DB_NAME")
DB_DRIVER = os.getenv("DB_DRIVER")
DB_TRUSTED_CONNECTION = os.getenv("DB_TRUSTED_CONNECTION", "yes")

conn_str = (
    f"DRIVER={{{DB_DRIVER}}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    f"Trusted_Connection={DB_TRUSTED_CONNECTION};"
    f"TrustServerCertificate=yes;"
)

# Change these two values to test
EMAIL_TO_CHECK = "debugtest@example.com"
PASSWORD_TO_TEST = "CHRist003#"

conn = pyodbc.connect(conn_str, timeout=5)
cursor = conn.cursor()
cursor.execute("SELECT email, hashed_password FROM dbo.users WHERE email = ?", EMAIL_TO_CHECK)
row = cursor.fetchone()

if not row:
    print(f"No user found with email: {EMAIL_TO_CHECK}")
else:
    stored_hash = row.hashed_password
    print(f"Found user: {row.email}")
    print(f"Stored hash: {stored_hash}")
    print(f"Stored hash length: {len(stored_hash)}")

    matches = bcrypt.checkpw(PASSWORD_TO_TEST.encode("utf-8"), stored_hash.encode("utf-8"))
    print(f"\nDoes '{PASSWORD_TO_TEST}' match the stored hash? -> {matches}")

conn.close()