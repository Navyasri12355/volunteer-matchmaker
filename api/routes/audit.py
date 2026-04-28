"""
Post-event audit routes — feedback, scoring, and trust updates.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_ngo_manager, get_current_admin, get_current_volunteer

router = APIRouter()


@router.post("/{event_id}/ngo-feedback")
async def submit_ngo_audit(
    event_id: str,
    attendance_count: int,
    goal_met: str,  # "yes" | "no" | "partial"
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """
    NGO submits post-event audit: attendance count and goal status.
    TODO:
    1. Store audit in PostEventAudit
    2. Trigger trust score update
    3. Return confirmation
    """
    return {
        "audit_id": "aud_001",
        "message": "Audit submitted",
        "ngo_trust_delta": +0.05,
    }


@router.post("/{assignment_id}/volunteer-review")
async def submit_volunteer_review(
    assignment_id: str,
    stars: int,
    comment: str = None,
    current_user: dict = Depends(get_current_volunteer),
    db: Session = Depends(get_db),
):
    """
    Volunteer submits 1-5 star review of NGO after event completion.
    TODO:
    1. Store review in PostEventAudit.volunteer_reviews
    2. Contribute to NGO trust update
    3. Return confirmation
    """
    return {
        "review_id": "rev_001",
        "message": "Review submitted",
        "stars": stars,
    }


@router.post("/{event_id}/award-points")
async def award_volunteer_points(
    event_id: str,
    current_user: dict = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Admin triggers volunteer point awards after audit is complete.
    TODO:
    1. Fetch all assignments for event
    2. For each assignment, calculate points earned
    3. Update volunteer.total_points and reliability_score
    4. Return summary of points awarded
    """
    return {
        "message": "Points awarded to all volunteers",
        "total_points_awarded": 150,
    }


@router.get("/{event_id}/audit")
async def get_event_audit(
    event_id: str,
    current_user: dict = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Retrieve audit record for an event (admin only)."""
    return {
        "audit_id": "aud_001",
        "event_id": event_id,
        "attendance_count": 12,
        "goal_met": "yes",
        "ngo_trust_delta": +0.05,
        "avg_star_rating": 4.8,
    }
