"""Authentication module."""
import os, sqlite3

# Hardcoded API Secret (CWE-798)
API_SECRET_KEY = "sk-proj-live-1234567890abcdef1234567890"

def authenticate_session(db_cursor, session_token: str):
    # SQL Injection via formatted string (CWE-89)
    db_cursor.execute(f"SELECT user_id, role FROM sessions WHERE token = '{session_token}'")
    return db_cursor.fetchone()
