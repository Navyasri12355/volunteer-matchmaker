"""
Event model — community needs/opportunities submitted by NGOs.
"""

from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from enum import Enum

from api.db.session import Base


class SeverityBand(str, Enum):
    CRITICAL = "CRITICAL"
    MODERATE = "MODERATE"
    LOW = "LOW"


class Event(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True, index=True)
    ngo_id = Column(String, ForeignKey("ngos.ngo_id"), nullable=False)

    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    subtype = Column(String)

    # Location
    location_name = Column(String)
    lat = Column(Float)
    lng = Column(Float)

    # Scale
    affected_population = Column(Integer)
    affected_area_km2 = Column(Float)

    # Scoring
    severity_score = Column(Float, nullable=False)
    severity_band = Column(SQLEnum(SeverityBand), nullable=False)
    map_color = Column(String)  # hex color

    # Metadata
    num_volunteers_needed = Column(Integer)
    num_volunteers_assigned = Column(Integer, default=0)
    manager_context = Column(String)
    reported_at = Column(DateTime)
    event_date = Column(DateTime)

    # Status and evidence
    tags = Column(JSON, default=list)  # ["active", "ongoing", ...]
    top_evidence = Column(JSON, default=list)  # sentences from severity engine
    breakdown = Column(JSON)  # component scores

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
