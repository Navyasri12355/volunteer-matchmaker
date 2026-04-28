"""
User model — base identity for all roles.
"""

from sqlalchemy import Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum

from api.db.session import Base
from api.core.constants import ROLE_ADMIN, ROLE_NGO_MANAGER, ROLE_VOLUNTEER


class UserRole(str, Enum):
    ADMIN = ROLE_ADMIN
    NGO_MANAGER = ROLE_NGO_MANAGER
    VOLUNTEER = ROLE_VOLUNTEER


class User(Base):
    __tablename__ = "users"

    firebase_uid = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(SQLEnum(UserRole), default=UserRole.VOLUNTEER)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
