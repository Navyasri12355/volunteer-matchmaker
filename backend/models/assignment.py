"""
Assignment helper class for state machine logic on assignments.

Manages the state machine: pending → accepted/rejected → (if accepted) attended/no_show

This helper works with the Assignment ORM model from backend.models.db_models
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional


class AssignmentStatus(str, Enum):
    """Valid assignment statuses."""

    PENDING = "pending"  # awaiting volunteer response (24h deadline)
    ACCEPTED = "accepted"  # volunteer accepted
    REJECTED = "rejected"  # volunteer rejected
    ATTENDED = "attended"  # confirmed volunteer attended event
    NO_SHOW = "no_show"  # volunteer assigned but did not attend


class AssignmentHelper:
    """
    Helper class for Assignment state machine logic.

    Use with the Assignment ORM model from backend.models.db_models.
    This class provides state transition methods.

    State machine
    ~~~~~~~~~~~~~
    pending  →  accepted / rejected
    accepted →  attended / no_show
    """

    @staticmethod
    def accept(assignment_orm) -> None:
        """Volunteer accepts the assignment."""
        if assignment_orm.status != AssignmentStatus.PENDING.value:
            raise ValueError(f"Cannot accept from status {assignment_orm.status}")
        assignment_orm.status = AssignmentStatus.ACCEPTED.value
        assignment_orm.responded_at = datetime.now(timezone.utc)

    @staticmethod
    def reject(assignment_orm) -> None:
        """Volunteer rejects the assignment."""
        if assignment_orm.status != AssignmentStatus.PENDING.value:
            raise ValueError(f"Cannot reject from status {assignment_orm.status}")
        assignment_orm.status = AssignmentStatus.REJECTED.value
        assignment_orm.responded_at = datetime.now(timezone.utc)

    @staticmethod
    def mark_attended(assignment_orm) -> None:
        """Record that volunteer attended the event."""
        if assignment_orm.status != AssignmentStatus.ACCEPTED.value:
            raise ValueError(f"Cannot mark attended from status {assignment_orm.status}")
        assignment_orm.status = AssignmentStatus.ATTENDED.value
        assignment_orm.attended_at = datetime.now(timezone.utc)

    @staticmethod
    def mark_no_show(assignment_orm) -> None:
        """Record that volunteer did not show up."""
        if assignment_orm.status != AssignmentStatus.ACCEPTED.value:
            raise ValueError(f"Cannot mark no_show from status {assignment_orm.status}")
        assignment_orm.status = AssignmentStatus.NO_SHOW.value
        assignment_orm.attended_at = datetime.now(timezone.utc)

    @staticmethod
    def is_expired(assignment_orm) -> bool:
        """Check if response deadline has passed."""
        return datetime.now(timezone.utc) > assignment_orm.deadline_at

    @staticmethod
    def is_early_accept(assignment_orm) -> bool:
        """Check if volunteer accepted within 24h of offering."""
        if assignment_orm.status != AssignmentStatus.ACCEPTED.value or not assignment_orm.responded_at:
            return False
        elapsed = assignment_orm.responded_at - assignment_orm.assigned_at
        return elapsed <= timedelta(hours=24)
