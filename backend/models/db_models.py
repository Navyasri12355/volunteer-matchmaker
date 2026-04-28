"""
SQLAlchemy ORM models matching schema.sql.

Maps database tables to Python classes for use with SQLAlchemy.
All models inherit from Base and use __tablename__ to match the schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    ARRAY,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class NGO(Base):
    """NGO organization table."""

    __tablename__ = "NGO"

    ngo_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
    trust_score = Column(Float, default=0.0)
    allowed_event_types = Column(ARRAY(String), nullable=True)
    blocked_event_types = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    events = relationship("Event", back_populates="ngo", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<NGO(ngo_id={self.ngo_id}, name={self.name})>"


class Volunteer(Base):
    """Volunteer table."""

    __tablename__ = "Volunteer"

    volunteer_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, unique=True)
    password_hash = Column(String(255), nullable=True)
    age = Column(Integer, nullable=True)
    skills = Column(ARRAY(String), nullable=True)
    certifications = Column(JSON, nullable=True)
    preferred_categories = Column(ARRAY(String), nullable=True)
    preferred_location = Column(String(255), nullable=True)
    max_travel_distance = Column(Float, nullable=True)
    reliability_score = Column(Float, default=0.0)
    volunteer_points = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    assignments = relationship("Assignment", back_populates="volunteer", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Volunteer(volunteer_id={self.volunteer_id}, name={self.name})>"


class Event(Base):
    """Event/opportunity table."""

    __tablename__ = "Event"

    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ngo_id = Column(String(36), ForeignKey("NGO.ngo_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    subtype = Column(String(100), nullable=True)
    location_name = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    area_size = Column(Float, nullable=True)
    severity_score = Column(Float, nullable=True)
    severity_level = Column(String(50), nullable=True)
    status = Column(String(50), nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    volunteers_required = Column(Integer, nullable=True)
    volunteers_assigned = Column(Integer, default=0)
    event_date = Column(DateTime(timezone=True), nullable=True)
    is_ongoing = Column(Boolean, default=True)
    supporting_docs = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    ngo = relationship("NGO", back_populates="events")
    assignments = relationship("Assignment", back_populates="event", cascade="all, delete-orphan")
    audits = relationship("Audit", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event(event_id={self.event_id}, title={self.title})>"


class Assignment(Base):
    """Volunteer-to-event assignment table."""

    __tablename__ = "Assignment"

    assignment_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("Event.event_id", ondelete="CASCADE"), nullable=False)
    volunteer_id = Column(String(36), ForeignKey("Volunteer.volunteer_id", ondelete="CASCADE"), nullable=False)
    assignment_type = Column(String(100), nullable=True)
    status = Column(String(50), default="pending")
    assigned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    responded_at = Column(DateTime(timezone=True), nullable=True)
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    attended_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    event = relationship("Event", back_populates="assignments")
    volunteer = relationship("Volunteer", back_populates="assignments")

    def __repr__(self):
        return f"<Assignment(assignment_id={self.assignment_id}, status={self.status})>"


class Audit(Base):
    """Post-event audit/review table."""

    __tablename__ = "Audit"

    audit_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), ForeignKey("Event.event_id", ondelete="CASCADE"), nullable=False)
    volunteer_id = Column(String(36), ForeignKey("Volunteer.volunteer_id", ondelete="CASCADE"), nullable=False)
    ngo_id = Column(String(36), ForeignKey("NGO.ngo_id", ondelete="CASCADE"), nullable=False)
    attendance = Column(Boolean, nullable=True)
    volunteer_rating = Column(Integer, nullable=True)
    ngo_rating = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)
    goal_achieved = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    event = relationship("Event", back_populates="audits")
    volunteer = relationship("Volunteer")
    ngo = relationship("NGO")

    def __repr__(self):
        return f"<Audit(audit_id={self.audit_id})>"

