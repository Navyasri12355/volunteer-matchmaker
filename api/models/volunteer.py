"""
Volunteer model — individual volunteers with skills and location.
"""

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from api.db.session import Base


class Volunteer(Base):
    __tablename__ = "volunteers"

    volunteer_id = Column(String, primary_key=True, index=True)
    firebase_uid = Column(String, ForeignKey("users.firebase_uid"), nullable=False)

    full_name = Column(String, nullable=False)
    phone = Column(String)
    age = Column(Integer)

    # Location
    city = Column(String)
    state = Column(String)
    lat = Column(Float)
    lng = Column(Float)
    willing_to_travel_km = Column(Integer, default=10)

    # Skills and preferences
    skills = Column(JSON, default=list)  # list of skill keys
    preferred_categories = Column(JSON, default=list)
    strengths = Column(String)
    past_experience = Column(String)

    # Scoring
    total_points = Column(Integer, default=0)
    reliability_score = Column(Float, default=1.0)
    is_verified = Column(Boolean, default=False)
    events_assigned = Column(Integer, default=0)
    events_attended = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
