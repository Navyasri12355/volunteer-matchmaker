"""Tests for volunteer models (VolunteerProfile, Assignment)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta, date
import pytest

from backend.models.volunteer import VolunteerProfile
from backend.models.assignment import Assignment, AssignmentStatus
from backend.nlp.skill_verifier import CertificateVerificationResult, VerificationStatus


def test_volunteer_profile_serialization_roundtrip() -> None:
    """Test VolunteerProfile → Firestore dict → VolunteerProfile."""
    profile = VolunteerProfile(
        volunteer_id="vol-123",
        name="Alice",
        email="alice@example.com",
        location_name="Bengaluru, India",
    )

    # Serialize
    firestore_dict = profile.to_firestore_dict()

    # Deserialize
    restored = VolunteerProfile.from_firestore_dict(firestore_dict)

    assert restored.volunteer_id == "vol-123"
    assert restored.name == "Alice"
    assert restored.email == "alice@example.com"
    assert restored.location_name == "Bengaluru, India"


def test_volunteer_profile_with_skills() -> None:
    """Test VolunteerProfile with verified skills."""
    profile = VolunteerProfile(
        volunteer_id="vol-456",
        name="Bob",
        email="bob@example.com",
        location_name="Mumbai, India",
    )

    # Add a skill
    cert = CertificateVerificationResult(
        volunteer_id="vol-456",
        skill_key="first_aid",
        status=VerificationStatus.VERIFIED,
        issue_date=datetime(2024, 1, 1).date(),
        expiry_date=datetime(2027, 1, 1).date(),  # future date
        verified_at=datetime.now(timezone.utc),
        ocr_text_snippet="First Aid Certificate",
        failure_reason="",
        requires_manual=False,
        storage_path="gs://bucket/certs/vol-456/first_aid.pdf",
    )

    profile.add_skill("first_aid", cert)

    assert profile.has_skill("first_aid")
    assert "first_aid" in profile.get_verified_skills()

    # Serialize and restore
    firestore_dict = profile.to_firestore_dict()
    restored = VolunteerProfile.from_firestore_dict(firestore_dict)

    assert restored.has_skill("first_aid")
    assert "first_aid" in restored.get_verified_skills()


def test_volunteer_profile_expired_skill() -> None:
    """Test that expired skills are not included in verified skills."""
    profile = VolunteerProfile(
        volunteer_id="vol-789",
        name="Charlie",
        email="charlie@example.com",
        location_name="Delhi, India",
    )

    # Add an expired skill
    cert = CertificateVerificationResult(
        volunteer_id="vol-789",
        skill_key="first_aid",
        status=VerificationStatus.VERIFIED,
        issue_date=datetime(2022, 1, 1).date(),
        expiry_date=datetime(2023, 1, 1).date(),  # expired
        verified_at=datetime(2022, 1, 1, tzinfo=timezone.utc),
        ocr_text_snippet="First Aid Certificate",
        failure_reason="",
        requires_manual=False,
        storage_path="gs://bucket/certs/vol-789/first_aid.pdf",
    )

    profile.add_skill("first_aid", cert)

    assert profile.has_skill("first_aid")
    assert "first_aid" not in profile.get_verified_skills()  # expired


def test_assignment_state_machine_accept() -> None:
    """Test Assignment state transitions: pending → accepted."""
    assignment = Assignment(
        assignment_id="asn-001",
        volunteer_id="vol-123",
        event_id="evt-001",
        status=AssignmentStatus.PENDING,
    )

    assert assignment.status == AssignmentStatus.PENDING
    assert assignment.responded_at is None

    assignment.accept()

    assert assignment.status == AssignmentStatus.ACCEPTED
    assert assignment.responded_at is not None


def test_assignment_state_machine_reject() -> None:
    """Test Assignment state transitions: pending → rejected."""
    assignment = Assignment(
        assignment_id="asn-002",
        volunteer_id="vol-123",
        event_id="evt-002",
    )

    assignment.reject()

    assert assignment.status == AssignmentStatus.REJECTED
    assert assignment.responded_at is not None


def test_assignment_state_machine_mark_attended() -> None:
    """Test Assignment: accepted → attended."""
    assignment = Assignment(
        assignment_id="asn-003",
        volunteer_id="vol-123",
        event_id="evt-003",
        status=AssignmentStatus.ACCEPTED,
    )

    assignment.mark_attended()

    assert assignment.status == AssignmentStatus.ATTENDED
    assert assignment.attended_at is not None


def test_assignment_state_machine_mark_no_show() -> None:
    """Test Assignment: accepted → no_show."""
    assignment = Assignment(
        assignment_id="asn-004",
        volunteer_id="vol-123",
        event_id="evt-004",
        status=AssignmentStatus.ACCEPTED,
    )

    assignment.mark_no_show()

    assert assignment.status == AssignmentStatus.NO_SHOW


def test_assignment_invalid_state_transition() -> None:
    """Test that invalid state transitions raise ValueError."""
    assignment = Assignment(
        assignment_id="asn-005",
        volunteer_id="vol-123",
        event_id="evt-005",
        status=AssignmentStatus.ACCEPTED,
    )

    # Can't reject an accepted assignment
    with pytest.raises(ValueError, match="Cannot reject"):
        assignment.reject()


def test_assignment_serialization_roundtrip() -> None:
    """Test Assignment → Firestore dict → Assignment."""
    now = datetime.now(timezone.utc)
    assignment = Assignment(
        assignment_id="asn-006",
        volunteer_id="vol-123",
        event_id="evt-006",
        status=AssignmentStatus.PENDING,
        offered_at=now,
        deadline_at=now + timedelta(hours=24),
    )

    # Serialize
    firestore_dict = assignment.to_firestore_dict()

    # Deserialize
    restored = Assignment.from_firestore_dict(firestore_dict)

    assert restored.assignment_id == "asn-006"
    assert restored.volunteer_id == "vol-123"
    assert restored.event_id == "evt-006"
    assert restored.status == AssignmentStatus.PENDING


def test_assignment_deadline_expiry() -> None:
    """Test assignment deadline checking."""
    now = datetime.now(timezone.utc)
    past = now - timedelta(hours=1)

    assignment = Assignment(
        assignment_id="asn-007",
        volunteer_id="vol-123",
        event_id="evt-007",
        offered_at=past,
        deadline_at=past,
    )

    assert assignment.is_expired()


def test_assignment_early_accept() -> None:
    """Test detection of early acceptance (within 24h)."""
    now = datetime.now(timezone.utc)

    assignment = Assignment(
        assignment_id="asn-008",
        volunteer_id="vol-123",
        event_id="evt-008",
        offered_at=now,
        deadline_at=now + timedelta(hours=24),
    )

    assignment.accept()

    assert assignment.is_early_accept()


def test_assignment_late_accept() -> None:
    """Test detection of late acceptance (after 24h)."""
    now = datetime.now(timezone.utc)
    offered = now - timedelta(hours=25)

    assignment = Assignment(
        assignment_id="asn-009",
        volunteer_id="vol-123",
        event_id="evt-009",
        offered_at=offered,
        deadline_at=offered + timedelta(hours=24),
        responded_at=now,
        status=AssignmentStatus.ACCEPTED,
    )

    assert not assignment.is_early_accept()
