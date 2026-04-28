"""
Initialize PostgreSQL database — create tables.

Run this script after setting DATABASE_URL env var:
    export DATABASE_URL=postgresql://user:password@localhost/volunteer_platform
    python scripts/init_db.py
"""

from pathlib import Path
import sys

# Ensure imports like `api.*` work even when script is invoked from outside repo root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine
from api.db.session import Base
from api.db.bootstrap import ensure_user_password_column
from api.core.config import settings
import api.models  # noqa: F401

def init_db():
    """Create all tables."""
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    ensure_user_password_column(engine)
    print("✓ Database tables created successfully")

if __name__ == "__main__":
    init_db()
