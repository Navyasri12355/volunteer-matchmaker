"""
Assignment routes — volunteer applications and confirmations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_volunteer, get_current_ngo_manager
from api.schemas.assignment import AssignmentResponse, ConfirmAssignmentRequest, ConfirmAssignmentResponse

router = APIRouter()


@router.post("/{event_id}/apply")
async def apply_to_event(
    event_id: str,
    current_user: dict = Depends(get_current_volunteer),
    db: Session = Depends(get_db),
):
    """
    Volunteer applies to a MODERATE or LOW severity event.
    TODO: Create Application record, return application_id.
    """
    return {"application_id": "app_001", "status": "pending"}


@router.post("/{assignment_id}/confirm", response_model=ConfirmAssignmentResponse)
async def confirm_assignment(
    assignment_id: str,
    req: ConfirmAssignmentRequest,
    current_user: dict = Depends(get_current_volunteer),
    db: Session = Depends(get_db),
):
    """
    Confirm or decline an assignment (for CRITICAL events auto-assigned to volunteer).
    TODO: Update Assignment.status and confirmed_at timestamp.
    """
    return ConfirmAssignmentResponse(
        assignment_id=assignment_id,
        status="accepted" if req.accept else "declined",
        confirmed_at="2025-06-14T12:00:00Z",
    )


@router.get("/{event_id}/volunteers")
async def list_event_applications(
    event_id: str,
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """
    List all volunteer applications for a MODERATE/LOW event.
    NGO manager can review and select volunteers.
    TODO: Return paginated list of applications with volunteer info.
    """
    return {
        "applications": [],
        "total": 0,
    }


@router.post("/{event_id}/select-volunteer")
async def select_volunteer_for_event(
    event_id: str,
    volunteer_id: str,
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """
    NGO manager selects a volunteer for an open call event.
    TODO: Create Assignment record with status ACCEPTED.
    """
    return {"assignment_id": "asgn_001", "status": "accepted"}
