"""
Assignment request/response schemas.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AssignmentResponse(BaseModel):
    assignment_id: str
    event_id: str
    volunteer_id: str
    status: str
    assigned_at: datetime
    confirmed_at: Optional[datetime]
    skill_matched: bool

    class Config:
        from_attributes = True


class ConfirmAssignmentRequest(BaseModel):
    accept: bool


class ConfirmAssignmentResponse(BaseModel):
    assignment_id: str
    status: str
    confirmed_at: datetime
