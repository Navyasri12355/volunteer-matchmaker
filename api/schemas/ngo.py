"""
NGO request/response schemas.
"""

from pydantic import BaseModel
from typing import Optional


class NGOProfileResponse(BaseModel):
    ngo_id: str
    org_name: str
    email: str
    org_registration_number: Optional[str]
    allowed_categories: list[str]
    custom_subtypes: dict[str, str]
    trust_score: float
    is_verified: bool
    is_suspended: bool

    class Config:
        from_attributes = True
