"""Integration tests for volunteer API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    with patch("backend.db.get_firestore_client") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        yield mock_db


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


def test_register_volunteer_success(client, mock_firestore):
    """Test successful volunteer registration."""
    # Mock Firestore operations
    mock_firestore.collection.return_value.where.return_value.stream.return_value = []  # No existing email

    response = client.post(
        "/api/volunteers/register",
        json={
            "name": "Alice Smith",
            "email": "alice@example.com",
            "location_name": "Bengaluru, India",
            "skills_interested": [],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Alice Smith"
    assert data["email"] == "alice@example.com"
    assert data["location_name"] == "Bengaluru, India"
    assert "volunteer_id" in data
    assert "created_at" in data


def test_register_volunteer_duplicate_email(client, mock_firestore):
    """Test registration fails for duplicate email."""
    # Mock: email already exists
    mock_doc = MagicMock()
    mock_firestore.collection.return_value.where.return_value.stream.return_value = [mock_doc]

    response = client.post(
        "/api/volunteers/register",
        json={
            "name": "Bob Smith",
            "email": "bob@example.com",
            "location_name": "Mumbai, India",
        },
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_register_volunteer_invalid_email(client):
    """Test registration fails for invalid email."""
    response = client.post(
        "/api/volunteers/register",
        json={
            "name": "Charlie",
            "email": "not-an-email",
            "location_name": "Delhi, India",
        },
    )

    assert response.status_code == 422  # Validation error


def test_match_volunteers_success(client, mock_firestore):
    """Test successful volunteer matching."""
    # Mock Firestore to return volunteer profiles
    mock_profile = {
        "profile": {
            "volunteer_id": "vol-001",
            "name": "Alice",
            "email": "alice@example.com",
            "location_name": "Bengaluru, India",
            "skills": {},
            "profile_created_at": "2025-01-01T00:00:00",
            "last_updated": "2025-01-01T00:00:00",
        }
    }

    mock_doc = MagicMock()
    mock_doc.id = "vol-001"
    mock_doc.get.return_value = mock_profile["profile"]

    mock_firestore.collection.return_value.stream.return_value = [mock_doc]

    response = client.post(
        "/api/volunteers/match",
        json={
            "event_category": "disaster_relief",
            "event_location": "Bengaluru, India",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "matches" in data
    assert "total" in data
    assert data["total"] >= 0


def test_assign_volunteer_success(client, mock_firestore):
    """Test successful assignment creation."""
    # Mock: volunteer exists
    mock_profile = {
        "volunteer_id": "vol-001",
        "name": "Alice",
        "email": "alice@example.com",
        "location_name": "Bengaluru, India",
        "skills": {},
    }

    # Mock Firestore document operations
    mock_firestore.document.return_value.get.return_value.exists = True
    mock_firestore.document.return_value.get.return_value.to_dict.return_value = {"volunteer_id": "vol-001"}

    mock_firestore.collection.return_value.where.return_value.where.return_value.stream.return_value = []  # No existing assignment

    response = client.post(
        "/api/volunteers/assign",
        json={
            "volunteer_id": "vol-001",
            "event_id": "evt-001",
            "event_category": "disaster_relief",
            "event_location": "Bengaluru, India",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "assignment_id" in data
    assert data["volunteer_id"] == "vol-001"
    assert data["event_id"] == "evt-001"
    assert data["status"] == "pending"
    assert "deadline" in data


def test_assign_volunteer_not_found(client, mock_firestore):
    """Test assignment fails when volunteer not found."""
    mock_firestore.document.return_value.get.return_value.exists = False

    response = client.post(
        "/api/volunteers/assign",
        json={
            "volunteer_id": "vol-nonexistent",
            "event_id": "evt-001",
            "event_category": "disaster_relief",
            "event_location": "Bengaluru, India",
        },
    )

    assert response.status_code == 400
    assert "not found" in response.json()["detail"]


def test_confirm_participation_accept(client, mock_firestore):
    """Test volunteer accepting an assignment."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=24)

    # Mock assignment doc
    assignment_data = {
        "assignment_id": "asn-001",
        "volunteer_id": "vol-001",
        "event_id": "evt-001",
        "status": "pending",
        "offered_at": now,
        "deadline_at": deadline,
        "responded_at": None,
        "attended_at": None,
    }

    mock_firestore.document.return_value.get.return_value.exists = True
    mock_firestore.document.return_value.get.return_value.to_dict.return_value = assignment_data

    response = client.post(
        "/api/volunteers/confirm-participation",
        json={
            "assignment_id": "asn-001",
            "confirmed": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["assignment_id"] == "asn-001"
    assert data["status"] == "accepted"
    assert "responded_at" in data


def test_confirm_participation_reject(client, mock_firestore):
    """Test volunteer rejecting an assignment."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=24)

    assignment_data = {
        "assignment_id": "asn-002",
        "volunteer_id": "vol-001",
        "event_id": "evt-001",
        "status": "pending",
        "offered_at": now,
        "deadline_at": deadline,
        "responded_at": None,
        "attended_at": None,
    }

    mock_firestore.document.return_value.get.return_value.exists = True
    mock_firestore.document.return_value.get.return_value.to_dict.return_value = assignment_data

    response = client.post(
        "/api/volunteers/confirm-participation",
        json={
            "assignment_id": "asn-002",
            "confirmed": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"


def test_confirm_participation_not_found(client, mock_firestore):
    """Test confirmation fails when assignment not found."""
    mock_firestore.document.return_value.get.return_value.exists = False

    response = client.post(
        "/api/volunteers/confirm-participation",
        json={
            "assignment_id": "asn-nonexistent",
            "confirmed": True,
        },
    )

    assert response.status_code == 400
    assert "not found" in response.json()["detail"]


def test_confirm_participation_already_responded(client, mock_firestore):
    """Test confirmation fails when already responded."""
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    earlier = now - timedelta(hours=1)

    assignment_data = {
        "assignment_id": "asn-003",
        "volunteer_id": "vol-001",
        "event_id": "evt-001",
        "status": "accepted",  # already responded
        "offered_at": earlier,
        "deadline_at": earlier + timedelta(hours=24),
        "responded_at": earlier,
        "attended_at": None,
    }

    mock_firestore.document.return_value.get.return_value.exists = True
    mock_firestore.document.return_value.get.return_value.to_dict.return_value = assignment_data

    response = client.post(
        "/api/volunteers/confirm-participation",
        json={
            "assignment_id": "asn-003",
            "confirmed": True,
        },
    )

    assert response.status_code == 409
    assert "already" in response.json()["detail"]
