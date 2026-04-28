"""
Seed database with demo data.

Usage:
    python scripts/seed_db.py
"""

from pathlib import Path
import sys

# Ensure imports like `api.*` work even when script is invoked from outside repo root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.config import settings
from api.db.session import Base
from api.models.user import User, UserRole
from api.models.ngo import NGO
from api.models.volunteer import Volunteer
from api.models.event import Event, SeverityBand

def seed_db():
    """Populate database with demo data."""
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create demo NGO user
    ngo_user = User(
        firebase_uid="ngo-demo-001",
        email="ngo@example.com",
        role=UserRole.NGO_MANAGER,
    )
    session.add(ngo_user)
    session.commit()

    # Create demo NGO
    ngo = NGO(
        ngo_id="ngo-001",
        firebase_uid="ngo-demo-001",
        org_name="Relief India",
        org_registration_number="MH/2019/0042",
        allowed_categories=["disaster_relief", "water_and_sanitation"],
        custom_subtypes={},
        trust_score=0.75,
        is_verified=True,
    )
    session.add(ngo)
    session.commit()

    # Create demo event
    event = Event(
        event_id="evt-001",
        ngo_id="ngo-001",
        title="Flood Relief - Assam Villages",
        category="disaster_relief",
        subtype="flood",
        location_name="Dhubri, Assam, India",
        lat=26.02,
        lng=89.97,
        affected_population=12000,
        affected_area_km2=85,
        severity_score=0.78,
        severity_band=SeverityBand.CRITICAL,
        map_color="#E53E3E",
        num_volunteers_needed=30,
        num_volunteers_assigned=5,
        manager_context="Three embankments breached on 14 June. 12,000 people displaced.",
        reported_at=datetime.now(timezone.utc) - timedelta(days=2),
        tags=["active"],
        top_evidence=[
            "Three embankments breached, 12,000 people displaced.",
            "No access to food or clean water for 48 hours.",
            "Medical emergency declared.",
        ],
    )
    session.add(event)
    session.commit()

    # Create demo volunteer
    vol_user = User(
        firebase_uid="vol-demo-001",
        email="volunteer@example.com",
        role=UserRole.VOLUNTEER,
    )
    session.add(vol_user)
    session.commit()

    volunteer = Volunteer(
        volunteer_id="vol-001",
        firebase_uid="vol-demo-001",
        full_name="Priya Sharma",
        phone="+91-9876543210",
        age=26,
        city="Bengaluru",
        state="Karnataka",
        lat=12.9716,
        lng=77.5946,
        willing_to_travel_km=50,
        skills=["first_aid", "teaching"],
        preferred_categories=["disaster_relief", "education"],
        total_points=250,
        reliability_score=0.92,
    )
    session.add(volunteer)
    session.commit()

    print("✓ Demo data seeded successfully")
    print(f"  NGO: {ngo.org_name} (ngo@example.com)")
    print(f"  Event: {event.title}")
    print(f"  Volunteer: {volunteer.full_name} (volunteer@example.com)")

if __name__ == "__main__":
    seed_db()
