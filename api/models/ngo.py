"""
NGO model — organizations managing community needs.
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from api.db.session import Base


class NGO(Base):
    __tablename__ = "ngos"

    ngo_id = Column(String, primary_key=True, index=True)
    firebase_uid = Column(String, ForeignKey("users.firebase_uid"), nullable=False)

    org_name = Column(String, nullable=False)
    org_registration_number = Column(String, unique=True)

    # Category permissions
    allowed_categories = Column(JSON, default=list)  # list of category keys
    custom_subtypes = Column(JSON, default=dict)     # {category_key: custom_label}

    # Trust scoring
    trust_score = Column(Float, default=0.5)
    is_verified = Column(Boolean, default=False)
    is_suspended = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
