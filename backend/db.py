"""
Database layer using SQLAlchemy ORM with PostgreSQL.

This module provides:
- SQLAlchemy engine and session factory
- Database initialization
- Session dependency for FastAPI
- Utility functions for common operations

Usage
~~~~~
    from backend.db import SessionLocal, get_db, init_db

    # In main.py
    init_db()

    # In API routes
    @app.get("/items")
    def read_items(db: Session = Depends(get_db)):
        return db.query(Item).all()
"""

from __future__ import annotations

import logging
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

from backend.config import settings

logger = logging.getLogger(__name__)

# ─── Database engine and session factory ──────────────────────────────────────

_engine: Engine = None
SessionLocal: sessionmaker = None


def get_engine() -> Engine:
    """Get or create SQLAlchemy engine."""
    global _engine
    if _engine is None:
        database_url = settings.database_url or "sqlite:///./test.db"
        logger.info(f"Connecting to database: {database_url[:50]}...")

        if database_url.startswith("sqlite"):
            _engine = create_engine(database_url, connect_args={"check_same_thread": False})
        else:
            # PostgreSQL
            _engine = create_engine(database_url, pool_pre_ping=True, echo=False)

        logger.info("Database engine created successfully")

    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create SQLAlchemy session factory."""
    global SessionLocal
    if SessionLocal is None:
        engine = get_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal


def init_db() -> None:
    """Initialize database (create tables)."""
    from backend.models.db_models import Base

    engine = get_engine()
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialization complete")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: get database session."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()

