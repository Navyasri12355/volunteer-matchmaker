"""
Audit model — post-event feedback and scoring updates.
"""

from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from api.db.session import Base


class PostEventAudit(Base):
    __tablename__ = "post_event_audits"

    audit_id = Column(String, primary_key=True, index=True)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=False)

    # NGO feedback
    attendance_count = Column(Integer)
    expected_count = Column(Integer)
    goal_met = Column(String)  # "yes" | "no" | "partial"

    # Volunteer feedback (aggregate)
    num_reviews = Column(Integer, default=0)
    avg_star_rating = Column(Float)
    volunteer_reviews = Column(JSON, default=list)  # list of {volunteer_id, stars, comment}

    # Trust score impact
    ngo_trust_delta = Column(Float)  # change applied to NGO trust score

    # Volunteer points awarded
    points_awarded = Column(JSON, default=dict)  # {volunteer_id: points}

    completed_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
