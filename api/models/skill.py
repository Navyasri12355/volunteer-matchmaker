"""
Skill model — volunteer skill verification and certificates.
"""

from sqlalchemy import Column, String, Date, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from enum import Enum

from api.db.session import Base


class SkillVerificationStatus(str, Enum):
    VERIFIED = "verified"
    PENDING_REVIEW = "pending_review"
    EXPIRED = "expired"
    REJECTED = "rejected"
    SELF_DECLARED = "self_declared"
    MISSING = "missing"


class SkillCertificate(Base):
    __tablename__ = "skill_certificates"

    certificate_id = Column(String, primary_key=True, index=True)
    volunteer_id = Column(String, ForeignKey("volunteers.volunteer_id"), nullable=False)

    skill_key = Column(String, nullable=False)
    status = Column(SQLEnum(SkillVerificationStatus), default=SkillVerificationStatus.SELF_DECLARED)

    issue_date = Column(Date)
    expiry_date = Column(Date)

    storage_path = Column(String)  # Firebase Storage path
    failure_reason = Column(String)
    requires_manual = Column(Boolean, default=False)

    verified_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
