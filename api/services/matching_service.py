"""
Matching service — volunteer-to-event assignment and ranking.
"""

import logging
import math
from sqlalchemy.orm import Session

from api.models.volunteer import Volunteer

logger = logging.getLogger(__name__)


class MatchingService:
    """Handles volunteer matching logic based on skills, location, reliability, and preferences."""

    @staticmethod
    def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        radius_km = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lng = math.radians(lng2 - lng1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(d_lng / 2) ** 2
        )
        return radius_km * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

    @staticmethod
    def _match_score(volunteer: Volunteer, event_category: str, event_lat: float, event_lng: float) -> tuple[float, str]:
        skills = {str(skill).lower() for skill in (volunteer.skills or [])}
        preferred_categories = {str(category).lower() for category in (volunteer.preferred_categories or [])}
        category = event_category.lower()

        skill_hit = category in skills or category in preferred_categories
        skill_score = 1.0 if skill_hit else 0.35 if skills or preferred_categories else 0.0

        distance_score = 0.5
        distance_text = "distance=unknown"
        if volunteer.lat is not None and volunteer.lng is not None and event_lat is not None and event_lng is not None:
            # Cast Column values to floats before calculation
            vol_lat: float = volunteer.lat  # type: ignore
            vol_lng: float = volunteer.lng  # type: ignore
            distance_km = MatchingService._haversine_km(vol_lat, vol_lng, event_lat, event_lng)
            willing_to_travel: int = volunteer.willing_to_travel_km or 0  # type: ignore
            travel_limit = max(float(willing_to_travel), 1.0)
            distance_score = max(0.0, min(1.0, 1.0 - (distance_km / (travel_limit * 2.0))))
            distance_text = f"distance={distance_km:.1f}km"

        # Cast Column values to Python types before math operations
        reliability_val: float = volunteer.reliability_score or 0.0  # type: ignore
        reliability = max(0.0, min(1.0, reliability_val))
        
        points_val: int = volunteer.total_points or 0  # type: ignore
        points_score = max(0.0, min(1.0, float(points_val) / 100.0))
        
        is_verified: bool = volunteer.is_verified or False  # type: ignore
        verification_score = 1.0 if is_verified else 0.7

        rank_score = round(
            0.35 * skill_score
            + 0.30 * reliability
            + 0.20 * distance_score
            + 0.10 * points_score
            + 0.05 * verification_score,
            4,
        )
        reason = (
            f"skills={'hit' if skill_hit else 'partial'}; "
            f"reliability={reliability:.2f}; {distance_text}; "
            f"points={volunteer.total_points or 0}"
        )
        return rank_score, reason

    @staticmethod
    def evaluate_volunteer_profile(volunteer: Volunteer, skill_key: str | None = None) -> dict:
        """Return a small matching summary for a single volunteer profile."""
        skills = {str(skill).lower() for skill in (volunteer.skills or [])}
        skill_hit = bool(skill_key and skill_key.lower() in skills)
        
        # Cast Column values to Python types before math operations
        reliability_val: float = volunteer.reliability_score or 0.0  # type: ignore
        reliability = max(0.0, min(1.0, reliability_val))
        
        points_val: int = volunteer.total_points or 0  # type: ignore
        points_score = max(0.0, min(1.0, float(points_val) / 100.0))

        overall = round(
            0.50 * reliability
            + 0.30 * (1.0 if skill_hit else 0.25 if skills else 0.0)
            + 0.20 * points_score,
            4,
        )

        return {
            "volunteer_id": volunteer.volunteer_id,
            "skill_key": skill_key,
            "skill_match": skill_hit,
            "reliability_score": reliability,
            "total_points": volunteer.total_points or 0,
            "match_score": overall,
        }

    @staticmethod
    async def rank_volunteers_for_event(
        db: Session,
        event_id: str,
        event_lat: float,
        event_lng: float,
        event_category: str,
        event_severity_band: str,
    ) -> list[dict]:
        """
        Rank volunteers for a given event based on:
        - Skill match (verified skills)
        - Geographic proximity (within travel_km)
        - Preferred category match
        - Reliability score (show-up rate)
        - Whether they've been assigned before for CRITICAL events

        Returns list of {volunteer_id, rank_score, reason}.
        """
        volunteers = db.query(Volunteer).all()
        ranked: list[dict] = []
        for volunteer in volunteers:
            score, reason = MatchingService._match_score(volunteer, event_category, event_lat, event_lng)
            if score <= 0:
                continue
            ranked.append(
                {
                    "volunteer_id": volunteer.volunteer_id,
                    "rank_score": score,
                    "reason": reason,
                    "reliability_score": volunteer.reliability_score,
                    "total_points": volunteer.total_points,
                }
            )

        ranked.sort(key=lambda item: item["rank_score"], reverse=True)
        return ranked[:20]

    @staticmethod
    async def auto_assign_critical_event(
        db: Session,
        event_id: str,
        top_volunteer_ids: list[str],
    ) -> list[str]:
        """
        Auto-assign top volunteers to a CRITICAL event.
        Volunteers must confirm within 24h or assignment is reassigned.

        Returns list of assignment_ids created.
        """
        return []

    @staticmethod
    async def handle_unconfirmed_assignments(db: Session, event_id: str) -> None:
        """Find assignments not confirmed within 24h and reassign."""
        # TODO: Implement reassignment logic
        pass
