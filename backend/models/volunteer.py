"""
VolunteerProfile helper class for volunteer data operations.

Works with the Volunteer ORM model from backend.models.db_models

Design follows the same pattern as before:
- Utility methods for working with volunteer data
- Certification verification result handling
- Skills management
"""

from __future__ import annotations

from datetime import datetime, timezone, date
from typing import Dict, List, Optional

from backend.nlp.skill_verifier import CertificateVerificationResult, VerificationStatus


class VolunteerProfile:
    """
    Helper for accessing Volunteer profile data and methods.

    Works with the Volunteer ORM model from backend.models.db_models.
    Provides utility methods for skill verification and profile operations.
    """

    def __init__(self, volunteer_orm):
        """Initialize with a Volunteer ORM object."""
        self.orm = volunteer_orm

    def has_skill(self, skill_key: str) -> bool:
        """Check if volunteer has a verified skill."""
        if not self.orm.skills:
            return False
        skills = self.orm.skills if isinstance(self.orm.skills, dict) else {}
        return skill_key in skills

    def get_verified_skills(self) -> List[str]:
        """Return list of skill keys that are verified and current."""
        if not self.orm.skills:
            return []

        skills = self.orm.skills if isinstance(self.orm.skills, dict) else {}
        verified = []

        for skill_key, cert_data in skills.items():
            # Check if status is VERIFIED
            status = cert_data.get("status") if isinstance(cert_data, dict) else getattr(cert_data, "status", None)
            is_verified = status == VerificationStatus.VERIFIED.value or status == VerificationStatus.VERIFIED

            # Check if not expired
            expiry_date = cert_data.get("expiry_date") if isinstance(cert_data, dict) else getattr(cert_data, "expiry_date", None)
            is_current = not expiry_date or expiry_date > datetime.now(timezone.utc).date()

            if is_verified and is_current:
                verified.append(skill_key)

        return verified

    @staticmethod
    def from_orm(volunteer_orm) -> VolunteerProfile:
        """Create a VolunteerProfile from a Volunteer ORM object."""
        return VolunteerProfile(volunteer_orm)
