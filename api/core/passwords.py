"""Password hashing and validation helpers."""

import re

from passlib.context import CryptContext

# Use bcrypt_sha256 to avoid the 72-byte bcrypt input limitation by
# pre-hashing long passwords with SHA-256 before bcrypt. This avoids
# truncation errors while remaining compatible with bcrypt verification.
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(password, password_hash)


def validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    # bcrypt (and some backends) have a 72-byte input limit; reject
    # overly long passwords early to avoid backend errors during hashing.
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password is too long (maximum 72 bytes). Please use a shorter password")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one number")