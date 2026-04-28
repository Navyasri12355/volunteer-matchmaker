"""
Dependency injection utilities.
"""

from typing import Generator

from fastapi import Depends, Header

from sqlalchemy.orm import Session
from api.db.session import get_db
from api.core.security import verify_firebase_token, extract_token_from_header


async def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> dict:
    """
    Extract and verify Firebase token from Authorization header.
    Returns decoded token claims (uid, email, etc.).
    """
    token = extract_token_from_header(authorization)
    claims = await verify_firebase_token(token)
    return claims


async def get_current_ngo_manager(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Ensure user is an NGO manager."""
    # TODO: Check user role in database
    return current_user


async def get_current_volunteer(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Ensure user is a volunteer."""
    # TODO: Check user role in database
    return current_user


async def get_current_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Ensure user is an admin."""
    # TODO: Check user role in database
    return current_user
