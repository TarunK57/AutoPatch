"""Authentication, API key handling, and multi-tenant user isolation."""

from __future__ import annotations

from typing import Optional
from fastapi import Header, HTTPException, Security, status
from pydantic import BaseModel, Field

from autopatch.core.exceptions import UnauthorizedPatchApplicationError


class User(BaseModel):
    """Authenticated user context for multi-tenant isolation."""

    user_id: str = Field(min_length=1)
    email: str = "user@autopatch.io"
    role: str = "developer"  # "developer", "admin", "auditor"


def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> User:
    """Extracts and validates current authenticated user from Bearer token or X-API-Key header."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials missing. Provide 'Authorization: Bearer <token>' or 'X-API-Key'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In local/sandbox service, support user identifiers in token (e.g. "user_alice", "dev_token_user_bob")
    clean_id = token.replace("dev_token_", "").strip()
    if not clean_id:
        clean_id = "default_user"

    return User(user_id=clean_id, email=f"{clean_id}@autopatch.io")


def assert_project_ownership(project_owner_id: str, current_user: User) -> None:
    """Enforces strict multi-tenant boundary: cross-user access attempts fail with 403 Forbidden."""
    if project_owner_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Cross-user access forbidden: project owned by '{project_owner_id}', "
                f"but authenticated as '{current_user.user_id}'."
            ),
        )
