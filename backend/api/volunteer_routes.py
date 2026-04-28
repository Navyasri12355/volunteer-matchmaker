"""
Volunteer registration, matching, and assignment API endpoints.

Exposes:
    POST /api/volunteers/register         → Register new volunteer
    POST /api/volunteers/match            → Find matches for an event
    POST /api/volunteers/assign           → Assign volunteer to event
    POST /api/volunteers/confirm-participation  → Volunteer accept/reject assignment
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db import get_db
from backend.models.db_models import Volunteer, Assignment, NGO, Event
from backend.matching.matcher import rank_volunteers_for_event
from backend.models.assignment import AssignmentStatus, AssignmentHelper

logger = logging.getLogger(__name__)

# ─── Pydantic models for request/response ────────────────────────────────────


class VolunteerRegistration(BaseModel):
    """Request payload for volunteer registration."""

    name: str
    email: EmailStr
    location_name: str = "Unknown"
    skills_interested: List[str] = []


class VolunteerResponse(BaseModel):
    """Response payload after volunteer registration."""

    volunteer_id: str
    name: str
    email: str
    created_at: str


class MatchRequest(BaseModel):
    """Request payload for finding matches."""

    event_category: str
    event_location: str


class MatchedVolunteer(BaseModel):
    """Single matched volunteer."""

    volunteer_id: str
    name: str
    match_score: float


class MatchedVolunteersResponse(BaseModel):
    """Response with list of matched volunteers."""

    matches: List[MatchedVolunteer]
    total: int


class AssignmentRequest(BaseModel):
    """Request payload for creating an assignment."""

    volunteer_id: str
    event_id: str
    event_category: str
    event_location: str


class AssignmentResponse(BaseModel):
    """Response after assignment creation."""

    assignment_id: str
    volunteer_id: str
    event_id: str
    status: str
    deadline: str


class ConfirmationRequest(BaseModel):
    """Request payload for confirming participation."""

    assignment_id: str
    confirmed: bool


class ConfirmationResponse(BaseModel):
    """Response after confirmation."""

    assignment_id: str
    status: str
    responded_at: str


# ─── Router setup ────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/volunteers", tags=["volunteers"])


# ─── Helper: notification placeholder ────────────────────────────────────────


async def _notify_volunteer(volunteer_id: str, event_id: str, assignment_id: str) -> None:
    """Placeholder for notification system. In production, send email/SMS."""
    logger.info(f"[NOTIFY] Assignment {assignment_id}: Volunteer {volunteer_id} assigned to event {event_id}")
    # TODO: Integrate with email/SMS service


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/register", response_model=VolunteerResponse, summary="Register a new volunteer")
async def register_volunteer(req: VolunteerRegistration, db: Session = Depends(get_db)):
    """
    Register a new volunteer.

    Creates a Volunteer record in PostgreSQL.
    """
    try:
        # Check if email already exists
        existing = db.query(Volunteer).filter(Volunteer.email == req.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        volunteer_id = f"vol-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        # Create volunteer record
        volunteer = Volunteer(
            volunteer_id=volunteer_id,
            name=req.name,
            email=req.email,
            preferred_location=req.location_name,
            created_at=now,
        )

        db.add(volunteer)
        db.commit()
        db.refresh(volunteer)

        logger.info(f"Registered new volunteer: {volunteer_id}")

        return VolunteerResponse(
            volunteer_id=volunteer_id,
            name=req.name,
            email=req.email,
            created_at=now.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Volunteer registration failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/match", response_model=MatchedVolunteersResponse, summary="Find matched volunteers for an event")
async def match_volunteers(req: MatchRequest, db: Session = Depends(get_db)):
    """
    Find ranked volunteers for a given event.

    Uses skill matching, location proximity, and reliability score.
    """
    try:
        matches = await rank_volunteers_for_event(
            event_category=req.event_category,
            event_location=req.event_location,
            max_results=10,
            db=db,
        )

        volunteers = [
            MatchedVolunteer(volunteer_id=vol_id, name=name, match_score=score)
            for vol_id, name, score in matches
        ]

        logger.info(f"Found {len(volunteers)} matches for {req.event_category} in {req.event_location}")

        return MatchedVolunteersResponse(matches=volunteers, total=len(volunteers))

    except Exception as exc:
        logger.exception("Matching failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/assign", response_model=AssignmentResponse, summary="Assign a volunteer to an event")
async def assign_volunteer(req: AssignmentRequest, db: Session = Depends(get_db)):
    """
    Create an assignment (offer event to volunteer).

    Sets a 24-hour deadline for the volunteer to respond.
    Triggers notification (placeholder).
    """
    try:
        # Verify volunteer exists
        volunteer = db.query(Volunteer).filter(Volunteer.volunteer_id == req.volunteer_id).first()
        if not volunteer:
            raise HTTPException(status_code=400, detail=f"Volunteer {req.volunteer_id} not found")

        # Check if already assigned (pending)
        existing = db.query(Assignment).filter(
            Assignment.volunteer_id == req.volunteer_id,
            Assignment.event_id == req.event_id,
            Assignment.status == AssignmentStatus.PENDING.value,
        ).first()

        if existing:
            raise HTTPException(status_code=409, detail="Volunteer already has pending assignment for this event")

        # Create assignment
        assignment_id = f"asn-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(hours=24)

        assignment = Assignment(
            assignment_id=assignment_id,
            volunteer_id=req.volunteer_id,
            event_id=req.event_id,
            status=AssignmentStatus.PENDING.value,
            assigned_at=now,
            deadline_at=deadline,
        )

        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        # Notify volunteer (placeholder)
        await _notify_volunteer(req.volunteer_id, req.event_id, assignment_id)

        logger.info(f"Created assignment {assignment_id}: {req.volunteer_id} → {req.event_id}")

        return AssignmentResponse(
            assignment_id=assignment_id,
            volunteer_id=req.volunteer_id,
            event_id=req.event_id,
            status=AssignmentStatus.PENDING.value,
            deadline=deadline.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Assignment failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/confirm-participation", response_model=ConfirmationResponse, summary="Volunteer confirms or rejects assignment"
)
async def confirm_participation(req: ConfirmationRequest, db: Session = Depends(get_db)):
    """
    Volunteer accepts or rejects an assignment.

    Updates assignment status in PostgreSQL.
    """
    try:
        # Get assignment
        assignment = db.query(Assignment).filter(Assignment.assignment_id == req.assignment_id).first()
        if not assignment:
            raise HTTPException(status_code=400, detail=f"Assignment {req.assignment_id} not found")

        # Check if already responded
        if assignment.status != AssignmentStatus.PENDING.value:
            raise HTTPException(status_code=409, detail=f"Assignment already {assignment.status}")

        # Check deadline
        if datetime.now(timezone.utc) > assignment.deadline_at:
            raise HTTPException(status_code=400, detail="Assignment deadline has passed")

        # Update assignment
        now = datetime.now(timezone.utc)
        if req.confirmed:
            assignment.status = AssignmentStatus.ACCEPTED.value
        else:
            assignment.status = AssignmentStatus.REJECTED.value

        assignment.responded_at = now

        db.commit()
        db.refresh(assignment)

        logger.info(
            f"Assignment {req.assignment_id}: Volunteer {assignment.volunteer_id} "
            f"{'accepted' if req.confirmed else 'rejected'}"
        )

        return ConfirmationResponse(
            assignment_id=req.assignment_id,
            status=assignment.status,
            responded_at=assignment.responded_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Confirmation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
