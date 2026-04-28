"""
VolunteerProfile dataclass for storing volunteer data in Firestore.

Follows the same pattern as NGOTrustScore and VolunteerPointsLedger:
- Firestore serialization via to_firestore_dict() / from_firestore_dict()
- Immutable fields + mutable state
- Optional datetime fields (Firestore natively supports them)

Firestore path: volunteers/{volunteer_id}/profile
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from typing import Dict, List, Optional

from backend.nlp.skill_verifier import CertificateVerificationResult, VerificationStatus


@dataclass
class VolunteerProfile:
    """
    Core profile data for a volunteer.

    Fields
    ------
    volunteer_id : str
        Unique identifier (e.g., "vol-abc123").
    name : str
        Volunteer's display name.
    email : str
        Contact email (should be unique).
    location_name : str
        City/region where volunteer is based (e.g., "Bengaluru, India").
    skills : Dict[str, CertificateVerificationResult]
        Map of skill_key → verification result for verified skills.
        Example: {"first_aid": CertificateVerificationResult(...)}
    profile_created_at : datetime
        When the profile was first created (tz-aware).
    last_updated : datetime
        Last profile update timestamp.
    """

    volunteer_id: str
    name: str
    email: str
    location_name: str
    skills: Dict[str, CertificateVerificationResult] = field(default_factory=dict)
    profile_created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ─── Firestore serialization ──────────────────────────────────────

    def to_firestore_dict(self) -> dict:
        """Serialize to Firestore-compatible dictionary."""
        return {
            "volunteer_id": self.volunteer_id,
            "name": self.name,
            "email": self.email,
            "location_name": self.location_name,
            "skills": {
                skill_key: {
                    "volunteer_id": cert.volunteer_id,
                    "skill_key": cert.skill_key,
                    "status": cert.status.value if isinstance(cert.status, VerificationStatus) else cert.status,
                    "issue_date": cert.issue_date,
                    "expiry_date": cert.expiry_date,
                    "verified_at": cert.verified_at,
                    "ocr_text_snippet": cert.ocr_text_snippet,
                    "failure_reason": cert.failure_reason,
                    "requires_manual": cert.requires_manual,
                    "storage_path": cert.storage_path,
                }
                for skill_key, cert in self.skills.items()
            },
            "profile_created_at": self.profile_created_at,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_firestore_dict(cls, data: dict) -> VolunteerProfile:
        """Deserialize from Firestore dictionary."""
        skills = {}
        for skill_key, cert_data in data.get("skills", {}).items():
            # Parse status as VerificationStatus enum
            status_str = cert_data["status"]
            status = VerificationStatus(status_str) if isinstance(status_str, str) else status_str

            skills[skill_key] = CertificateVerificationResult(
                volunteer_id=cert_data["volunteer_id"],
                skill_key=cert_data["skill_key"],
                status=status,
                issue_date=cert_data.get("issue_date"),
                expiry_date=cert_data.get("expiry_date"),
                verified_at=cert_data.get("verified_at"),
                ocr_text_snippet=cert_data.get("ocr_text_snippet", ""),
                failure_reason=cert_data.get("failure_reason", ""),
                requires_manual=cert_data.get("requires_manual", False),
                storage_path=cert_data.get("storage_path", ""),
            )

        return cls(
            volunteer_id=data["volunteer_id"],
            name=data["name"],
            email=data["email"],
            location_name=data["location_name"],
            skills=skills,
            profile_created_at=data.get("profile_created_at", datetime.now(timezone.utc)),
            last_updated=data.get("last_updated", datetime.now(timezone.utc)),
        )

    # ─── Convenience methods ──────────────────────────────────────────

    def has_skill(self, skill_key: str) -> bool:
        """Check if volunteer has a verified skill."""
        return skill_key in self.skills

    def add_skill(self, skill_key: str, cert_result: CertificateVerificationResult) -> None:
        """Add or update a verified skill."""
        self.skills[skill_key] = cert_result
        self.last_updated = datetime.now(timezone.utc)

    def get_verified_skills(self) -> List[str]:
        """Return list of skill keys that are verified and current."""
        verified = []
        for skill_key, cert in self.skills.items():
            # Check if status is VERIFIED
            is_verified = cert.status == VerificationStatus.VERIFIED
            # Check if not expired
            is_current = not cert.expiry_date or cert.expiry_date > datetime.now(timezone.utc).date()

            if is_verified and is_current:
                verified.append(skill_key)

        return verified

