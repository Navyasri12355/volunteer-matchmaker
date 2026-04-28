"""
Event request/response schemas.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CreateEventRequest(BaseModel):
    title: str
    category: str
    subtype: Optional[str] = None
    location_name: str
    lat: float
    lng: float
    affected_population: Optional[int] = None
    affected_area_km2: Optional[float] = None
    num_volunteers_needed: int
    manager_context: Optional[str] = None
    reported_at: Optional[datetime] = None


class EventResponse(BaseModel):
    event_id: str
    title: str
    category: str
    subtype: Optional[str]
    location_name: str
    lat: float
    lng: float
    severity_score: float
    severity_band: str
    map_color: str
    num_volunteers_needed: int
    num_volunteers_assigned: int
    tags: list[str]
    top_evidence: list[str]
    ngo_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    events: list[EventResponse]
    next_cursor: Optional[str] = None
