"""
Firebase token verification and security utilities.
"""

import logging
from typing import Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


async def verify_firebase_token(token: str) -> dict:
    """
    Verify a Firebase ID token.
    In production, use firebase_admin.auth.verify_id_token().
    For now, this is a stub that should be replaced with real Firebase verification.
    """
    # TODO: Implement Firebase token verification
    # This requires:
    # - firebase_admin SDK initialized
    # - GOOGLE_APPLICATION_CREDENTIALS set
    # Example:
    #   import firebase_admin
    #   from firebase_admin import auth
    #   decoded_token = auth.verify_id_token(token)
    #   return decoded_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )
    # Local-dev token format issued by /auth/login:
    #   local:<firebase_uid>:<role>
    # This lets protected routes resolve the real user record in PostgreSQL.
    if token.startswith("local:"):
        parts = token.split(":", 2)
        if len(parts) != 3 or not parts[1]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid local auth token",
            )
        uid = parts[1]
        role = parts[2]
        return {"uid": uid, "role": role, "email": uid}

    # Fallback stub for legacy tokens in local development.
    return {"uid": "test-user", "email": "test@example.com"}


def extract_token_from_header(auth_header: Optional[str]) -> str:
    """Extract Bearer token from Authorization header."""
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
        )
    return auth_header.split(" ", 1)[1]
