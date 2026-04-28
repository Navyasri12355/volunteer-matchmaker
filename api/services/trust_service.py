"""
Trust service — NGO trust scoring and volunteer points management.
"""

import logging
from sqlalchemy.orm import Session
from api.models.ngo import NGO
from api.models.volunteer import Volunteer
from backend.nlp.trust_scorer import TrustScorer, NGOTrustScore, VolunteerPointsLedger

logger = logging.getLogger(__name__)


class TrustService:
    """Wraps backend.nlp.trust_scorer and integrates with PostgreSQL."""

    def __init__(self, db_client=None):
        self.scorer = TrustScorer(db_client=db_client)

    async def update_ngo_trust_from_audit(
        self,
        db: Session,
        ngo_id: str,
        star_rating: float,
        goal_met: bool,
        attendance_ratio: float,
    ) -> dict:
        """
        Update NGO trust score after a post-event audit.
        Uses exponential moving average to smooth out single bad events.

        Returns updated trust score info.
        """
        trust = await self.scorer.apply_audit_to_ngo(
            ngo_id=ngo_id,
            star_rating=star_rating,
            goal_met=goal_met,
            attendance_ratio=attendance_ratio,
        )

        ngo = db.query(NGO).filter(NGO.ngo_id == ngo_id).first()
        if ngo:
            ngo.trust_score = trust.composite_score
            ngo.is_verified = trust.is_verified
            ngo.is_suspended = trust.is_suspended
            db.commit()

        return trust.to_firestore_dict()

    async def award_volunteer_points(
        self,
        db: Session,
        volunteer_id: str,
        event_id: str,
        severity_band: str,
        goal_met: bool,
        skill_used: bool,
        early_accept: bool,
        ngo_star_rating: float,
    ) -> int:
        """
        Award points to a volunteer after event completion.

        Returns points earned.
        """
        earned = await self.scorer.award_event_points(
            volunteer_id=volunteer_id,
            event_id=event_id,
            severity_band=severity_band,
            goal_met=goal_met,
            skill_used=skill_used,
            early_accept=early_accept,
            ngo_star_rating=ngo_star_rating,
        )

        ledger = await self.scorer.get_volunteer_ledger(volunteer_id)
        volunteer = db.query(Volunteer).filter(Volunteer.volunteer_id == volunteer_id).first()
        if volunteer:
            volunteer.total_points = ledger.total_points
            volunteer.reliability_score = ledger.reliability_score
            volunteer.events_assigned = ledger.events_assigned
            volunteer.events_attended = ledger.events_attended
            db.commit()

        return earned

    async def check_ngo_can_create_event(
        self,
        db: Session,
        ngo_id: str,
    ) -> tuple[bool, str]:
        """
        Gate check: can this NGO create a new event?
        Must have trust_score >= 0.40.

        Returns (allowed, reason).
        """
        ngo = db.query(NGO).filter(NGO.ngo_id == ngo_id).first()
        if not ngo:
            return False, "NGO not found"

        trust = NGOTrustScore(ngo_id=ngo.ngo_id, composite_score=float(ngo.trust_score or 0.0))
        trust.is_verified = bool(ngo.is_verified)
        trust.is_suspended = bool(ngo.is_suspended)
        return trust.can_create_event()
