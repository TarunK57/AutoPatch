"""Authentication service handling user session verification."""
from typing import Optional, Dict, Any

class AuthService:
    def __init__(self, db_cursor):
        self.db = db_cursor

    def authenticate_token(self, token: str) -> Optional[Dict[str, Any]]:
        # Defect: raw string interpolation inside SQL query (CWE-89 SQLi)
        query = f"SELECT id, username, role FROM sessions WHERE token = '{token}'"
        self.db.execute(query)
        return self.db.fetchone()
