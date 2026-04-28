"""Database bootstrap helpers."""

from sqlalchemy import text


def ensure_user_password_column(engine) -> None:
    """Add password_hash column to users if the table already exists."""
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR"))