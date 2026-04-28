"""Tests for volunteer matching algorithm."""

from __future__ import annotations

from datetime import datetime, timezone, date
import pytest

from backend.models.volunteer import VolunteerProfile
from backend.matching.matcher import (
    _location_distance_score,
    _skill_match_score,
)


def test_location_distance_same_city() -> None:
    """Test distance scoring for same location."""
    score = _location_distance_score("Bengaluru, India", "Bengaluru, India")
    assert score == 1.0


def test_location_distance_substring_match() -> None:
    """Test distance scoring when one is substring of other."""
    score = _location_distance_score("Bengaluru", "Bengaluru, India")
    assert score == 0.9


def test_location_distance_different_cities() -> None:
    """Test distance scoring for different cities."""
    score = _location_distance_score("Bengaluru, India", "Mumbai, India")
    assert score == 0.3


def test_location_distance_case_insensitive() -> None:
    """Test that location matching is case-insensitive."""
    score = _location_distance_score("BENGALURU, INDIA", "bengaluru, india")
    assert score == 1.0


def test_location_distance_empty_location() -> None:
    """Test distance scoring when location is empty."""
    score = _location_distance_score("", "Bengaluru, India")
    assert score == 0.5

    score = _location_distance_score("Bengaluru, India", "")
    assert score == 0.5


def test_skill_match_no_skills() -> None:
    """Test skill matching for volunteer with no skills."""
    profile = VolunteerProfile(
        volunteer_id="vol-001",
        name="Alice",
        email="alice@example.com",
        location_name="Bengaluru, India",
    )

    score = _skill_match_score(profile, "disaster_relief")
    assert score == 0.0


def test_skill_match_unrelated_skill() -> None:
    """Test skill matching when volunteer has unrelated skills."""
    from backend.nlp.skill_verifier import CertificateVerificationResult, VerificationStatus

    profile = VolunteerProfile(
        volunteer_id="vol-002",
        name="Bob",
        email="bob@example.com",
        location_name="Mumbai, India",
    )

    # Add a skill not related to disaster_relief
    cert = CertificateVerificationResult(
        volunteer_id="vol-002",
        skill_key="food_safety",
        status=VerificationStatus.VERIFIED,
        issue_date=datetime(2024, 1, 1).date(),
        expiry_date=datetime(2027, 1, 1).date(),
        verified_at=datetime.now(timezone.utc),
        ocr_text_snippet="Food Safety",
        failure_reason="",
        requires_manual=False,
        storage_path="gs://bucket/certs/vol-002/food_safety.pdf",
    )

    profile.add_skill("food_safety", cert)

    score = _skill_match_score(profile, "disaster_relief")
    assert score == 0.5  # has skills but not for this category


def test_skill_match_relevant_skill() -> None:
    """Test skill matching when volunteer has relevant skill."""
    from backend.nlp.skill_verifier import CertificateVerificationResult, VerificationStatus

    profile = VolunteerProfile(
        volunteer_id="vol-003",
        name="Charlie",
        email="charlie@example.com",
        location_name="Delhi, India",
    )

    # Add a first_aid skill (relevant to disaster_relief)
    cert = CertificateVerificationResult(
        volunteer_id="vol-003",
        skill_key="first_aid",
        status=VerificationStatus.VERIFIED,
        issue_date=datetime(2024, 1, 1).date(),
        expiry_date=datetime(2027, 1, 1).date(),
        verified_at=datetime.now(timezone.utc),
        ocr_text_snippet="First Aid",
        failure_reason="",
        requires_manual=False,
        storage_path="gs://bucket/certs/vol-003/first_aid.pdf",
    )

    profile.add_skill("first_aid", cert)

    score = _skill_match_score(profile, "disaster_relief")
    assert score == 1.0  # exact match


def test_skill_match_education_category() -> None:
    """Test skill matching for education category."""
    from backend.nlp.skill_verifier import CertificateVerificationResult, VerificationStatus

    profile = VolunteerProfile(
        volunteer_id="vol-004",
        name="Dave",
        email="dave@example.com",
        location_name="Bangalore, India",
    )

    # Add a teaching skill
    cert = CertificateVerificationResult(
        volunteer_id="vol-004",
        skill_key="teaching",
        status=VerificationStatus.VERIFIED,
        issue_date=datetime(2024, 1, 1).date(),
        expiry_date=datetime(2027, 1, 1).date(),
        verified_at=datetime.now(timezone.utc),
        ocr_text_snippet="Teaching Certificate",
        failure_reason="",
        requires_manual=False,
        storage_path="gs://bucket/certs/vol-004/teaching.pdf",
    )

    profile.add_skill("teaching", cert)

    score = _skill_match_score(profile, "education")
    assert score == 1.0
