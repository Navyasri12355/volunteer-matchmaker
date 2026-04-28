"""
Volunteer matching algorithm for finding best-fit volunteers for events.

Match score = skill_match × distance_factor × reliability_multiplier

- skill_match: 1.0 if has verified skill for category, 0.5 if has unrelated skills, 0.0 if no skills
- distance_factor: 1.0 if same location, decays with distance
- reliability_multiplier: 1.0 if reliable (≥0.60), 0.5 if unreliable

Returns list of (volunteer_id, match_score) sorted by score descending.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from backend.db import get_firestore_client, query_documents
from backend.models.volunteer import VolunteerProfile
from backend.nlp.category_config import CATEGORIES
from backend.nlp.trust_scorer import VolunteerPointsLedger

logger = logging.getLogger(__name__)

# ─── Location distance scoring ────────────────────────────────────────────────
# Simple heuristic without geocoding API: same location = 1.0, different = 0.3


def _location_distance_score(volunteer_location: str, event_location: str) -> float:
    """
    Simple location matching score without geocoding.

    Same city/region = 1.0, different = 0.3 (assume some distance but still possible).
    In production, replace with haversine distance calculation if lat/lng available.
    """
    if not volunteer_location or not event_location:
        return 0.5  # unknown location

    vol_lower = volunteer_location.lower().strip()
    evt_lower = event_location.lower().strip()

    if vol_lower == evt_lower:
        return 1.0

    # Simple heuristic: if either is a substring of the other (e.g., "Bengaluru" in "Bengaluru, India")
    if vol_lower in evt_lower or evt_lower in vol_lower:
        return 0.9

    # Different locations
    return 0.3


# ─── Skill matching ──────────────────────────────────────────────────────────


def _skill_match_score(volunteer_profile: VolunteerProfile, event_category: str) -> float:
    """
    Score based on volunteer's skills matching the event category.

    Rules:
    - 1.0 if volunteer has verified skill for this category
    - 0.5 if volunteer has some skills but not for this category (shows commitment)
    - 0.0 if volunteer has no skills at all
    """
    verified_skills = volunteer_profile.get_verified_skills()

    if not verified_skills:
        return 0.0  # no skills

    # Check if volunteer has skill for this specific category
    # Map event category → skill keys that match
    category_skill_map = {
        "disaster_relief": ["first_aid", "rescue"],
        "water_and_sanitation": ["first_aid", "sanitation"],
        "food": ["food_safety", "nutrition"],
        "education": ["teaching", "tutoring"],
        "environment": ["environmental"],
        "animal_welfare": ["veterinary", "animal_care"],
    }

    matching_skills = category_skill_map.get(event_category, [])

    if any(skill in verified_skills for skill in matching_skills):
        return 1.0  # exact match for category

    return 0.5  # has skills, but not for this category


# ─── Reliability scoring ─────────────────────────────────────────────────────


async def _reliability_multiplier(volunteer_id: str) -> float:
    """
    Look up volunteer's reliability score.

    1.0 if reliable (≥ 0.60), 0.5 if unreliable.
    New volunteers (no assignments) are optimistic at 1.0.
    """
    try:
        db = await get_firestore_client()
        doc = db.document(f"volunteers/{volunteer_id}/points_ledger").get()
        if not doc.exists:
            return 1.0  # new volunteer, optimistic

        data = doc.to_dict()
        ledger = VolunteerPointsLedger.from_firestore_dict(data)

        return 1.0 if ledger.is_reliable() else 0.5
    except Exception as exc:
        logger.warning("Failed to fetch reliability for %s: %s", volunteer_id, exc)
        return 0.5  # default to unreliable if lookup fails


# ─── Main ranking function ───────────────────────────────────────────────────


async def rank_volunteers_for_event(
    event_category: str,
    event_location: str,
    max_results: int = 10,
) -> List[Tuple[str, str, float]]:
    """
    Find and rank all volunteers for a given event.

    Parameters
    ----------
    event_category : str
        Event category (e.g., "disaster_relief").
    event_location : str
        Event location string (e.g., "Assam, India").
    max_results : int
        Return top N matches.

    Returns
    -------
    List[Tuple[volunteer_id, volunteer_name, match_score]]
        Sorted by match_score descending.
    """
    try:
        db = await get_firestore_client()

        # Fetch all volunteer profiles
        volunteers_ref = db.collection("volunteers")
        profiles = []

        for doc in volunteers_ref.stream():
            profile_data = doc.get("profile")
            if profile_data:
                try:
                    profile = VolunteerProfile.from_firestore_dict(profile_data)
                    profiles.append(profile)
                except Exception as exc:
                    logger.warning("Failed to load profile for %s: %s", doc.id, exc)

        logger.info(f"Found {len(profiles)} volunteer profiles")

        # Compute match scores
        matches: List[Tuple[str, str, float]] = []

        for profile in profiles:
            # Compute three factors
            skill_score = _skill_match_score(profile, event_category)
            distance_score = _location_distance_score(profile.location_name, event_location)
            reliability_score = await _reliability_multiplier(profile.volunteer_id)

            # Composite score (product of all three)
            composite_score = skill_score * distance_score * reliability_score

            matches.append((profile.volunteer_id, profile.name, composite_score))

            logger.debug(
                f"Volunteer {profile.name}: skill={skill_score:.2f}, "
                f"distance={distance_score:.2f}, reliability={reliability_score:.2f}, "
                f"composite={composite_score:.4f}"
            )

        # Sort by score descending
        matches.sort(key=lambda x: x[2], reverse=True)

        # Return top N
        return matches[:max_results]

    except Exception as exc:
        logger.exception("Matching failed for %s in %s: %s", event_category, event_location, exc)
        return []
