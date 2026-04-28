"""
Assignment model — volunteer assignments to events.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Enum as SQLEnum
from sqlalchemy.sql import func
from enum import Enum

from api.db.session import Base


class AssignmentStatus(str, Enum):
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Assignment(Base):
    __tablename__ = "assignments"

    assignment_id = Column(String, primary_key=True, index=True)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=False)
    volunteer_id = Column(String, ForeignKey("volunteers.volunteer_id"), nullable=False)

    status = Column(SQLEnum(AssignmentStatus), default=AssignmentStatus.ASSIGNED)

    # For CRITICAL events, volunteers must confirm within 24h
    assigned_at = Column(DateTime, server_default=func.now())
    confirmed_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Flags
    skill_matched = Column(Boolean, default=False)
    was_early_accept = Column(Boolean, default=False)  # confirmed within 24h

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
