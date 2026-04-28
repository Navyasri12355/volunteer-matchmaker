"""
Assignment dataclass for tracking volunteer-to-event assignments.

Manages the state machine: pending → accepted/rejected → (if accepted) attended/no_show

Firestore path: assignments/{assignment_id}
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class Assignment:
    """
    Represents a single volunteer-to-event assignment.

    Fields
    ------
    assignment_id : str
        Unique identifier (e.g., "asn-xyz789").
    volunteer_id : str
        Volunteer being assigned.
    event_id : str
        Event being assigned.
    status : AssignmentStatus
        Current status in state machine.
    offered_at : datetime
        When the assignment was created/offered.
    deadline_at : datetime
        Deadline for volunteer to respond (typically offered_at + 24h).
    responded_at : Optional[datetime]
        When volunteer confirmed/rejected (None until response).
    attended_at : Optional[datetime]
        When event completion was recorded (None until attendance confirmed).

    State machine
    ~~~~~~~~~~~~~
    pending  →  accepted / rejected
    accepted →  attended / no_show
    """

    assignment_id: str
    volunteer_id: str
    event_id: str
    status: AssignmentStatus = AssignmentStatus.PENDING
    offered_at: datetime = None
    deadline_at: datetime = None
    responded_at: Optional[datetime] = None
    attended_at: Optional[datetime] = None

    def __post_init__(self):
        """Set default timestamps if not provided."""
        if self.offered_at is None:
            self.offered_at = datetime.now(timezone.utc)
        if self.deadline_at is None:
            self.deadline_at = self.offered_at + timedelta(hours=24)

    # ─── Firestore serialization ──────────────────────────────────────

    def to_firestore_dict(self) -> dict:
        """Serialize to Firestore-compatible dictionary."""
        return {
            "assignment_id": self.assignment_id,
            "volunteer_id": self.volunteer_id,
            "event_id": self.event_id,
            "status": self.status.value,
            "offered_at": self.offered_at,
            "deadline_at": self.deadline_at,
            "responded_at": self.responded_at,
            "attended_at": self.attended_at,
        }

    @classmethod
    def from_firestore_dict(cls, data: dict) -> Assignment:
        """Deserialize from Firestore dictionary."""
        return cls(
            assignment_id=data["assignment_id"],
            volunteer_id=data["volunteer_id"],
            event_id=data["event_id"],
            status=AssignmentStatus(data.get("status", "pending")),
            offered_at=data.get("offered_at", datetime.now(timezone.utc)),
            deadline_at=data.get("deadline_at", datetime.now(timezone.utc) + timedelta(hours=24)),
            responded_at=data.get("responded_at"),
            attended_at=data.get("attended_at"),
        )

    # ─── State machine methods ────────────────────────────────────────

    def accept(self) -> None:
        """Volunteer accepts the assignment."""
        if self.status != AssignmentStatus.PENDING:
            raise ValueError(f"Cannot accept from status {self.status}")
        self.status = AssignmentStatus.ACCEPTED
        self.responded_at = datetime.now(timezone.utc)

    def reject(self) -> None:
        """Volunteer rejects the assignment."""
        if self.status != AssignmentStatus.PENDING:
            raise ValueError(f"Cannot reject from status {self.status}")
        self.status = AssignmentStatus.REJECTED
        self.responded_at = datetime.now(timezone.utc)

    def mark_attended(self) -> None:
        """Record that volunteer attended the event."""
        if self.status != AssignmentStatus.ACCEPTED:
            raise ValueError(f"Cannot mark attended from status {self.status}")
        self.status = AssignmentStatus.ATTENDED
        self.attended_at = datetime.now(timezone.utc)

    def mark_no_show(self) -> None:
        """Record that volunteer did not show up."""
        if self.status != AssignmentStatus.ACCEPTED:
            raise ValueError(f"Cannot mark no_show from status {self.status}")
        self.status = AssignmentStatus.NO_SHOW
        self.attended_at = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        """Check if response deadline has passed."""
        return datetime.now(timezone.utc) > self.deadline_at

    def is_early_accept(self) -> bool:
        """Check if volunteer accepted within 24h of offering."""
        if self.status != AssignmentStatus.ACCEPTED or not self.responded_at:
            return False
        elapsed = self.responded_at - self.offered_at
        return elapsed <= timedelta(hours=24)
