"""
Volunteer request/response schemas.
"""

from pydantic import BaseModel
from typing import Optional


class VolunteerProfileResponse(BaseModel):
    volunteer_id: str
    full_name: str
    email: str
    phone: Optional[str]
    age: Optional[int]
    city: Optional[str]
    state: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    willing_to_travel_km: int
    skills: list[str]
    preferred_categories: list[str]
    total_points: int
    reliability_score: float

    class Config:
        from_attributes = True


class SkillCertificateResponse(BaseModel):
    skill_key: str
    status: str
    issue_date: Optional[str]
    expiry_date: Optional[str]
    requires_manual: bool

    class Config:
        from_attributes = True
