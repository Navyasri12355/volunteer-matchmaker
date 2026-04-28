"""
backend/api/map_routes.py
--------------------------
FastAPI router that serves event data for the MapView.jsx frontend.

Exposes:
    GET /api/events/map   →  list of GeoJSON-style features, one per event,
                             shaped by build_map_marker() from severity_engine.py

How it connects to your existing pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Ingestor  →  chunks of text
    EventNLPExtractor  →  ExtractedEntities (locations, urgency, population…)
    SeverityEngine     →  SeverityResult   (score, band, color, radius_m…)
    build_map_marker() →  GeoJSON feature  (what MapView.jsx expects)

The route takes EventInput objects (or a simple POST body), runs them through
the pipeline, and returns the map-ready JSON.

Alternatively, if you store scored events in Firestore / a database,
swap the `_run_demo_pipeline()` section with a DB fetch.

Usage
~~~~~
    uvicorn backend.api.map_routes:app --host 0.0.0.0 --port 8080 --reload

    Or mount this router in your main FastAPI app:
        from backend.api.map_routes import router
        app.include_router(router)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel

from backend.config import settings
from backend.nlp.severity_engine import (
    EventInput,
    SeverityEngine,
    build_map_marker,
)
from backend.nlp.event_nlp_extractor import EventNLPExtractor

logger = logging.getLogger(__name__)

# ─── Router ──────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/events", tags=["map"])

# ─── Pydantic schemas (for POST /api/events/map/score) ───────────────────────

class EventSubmission(BaseModel):
    """
    Payload for scoring a new event on the fly.
    Mirrors EventInput but serialisable.
    """
    id:                  Optional[str]   = None
    category:            str
    subtype:             Optional[str]   = None
    document_texts:      List[str]       = []
    manager_context:     str             = ""
    location_name:       str             = ""
    affected_population: Optional[int]   = None
    affected_area_km2:   Optional[float] = None
    num_supporting_docs: int             = 1
    reported_at:         Optional[str]   = None  # ISO 8601 string
    language:            Optional[str]   = None


class MapEventResponse(BaseModel):
    """Single map-ready event (GeoJSON-style feature + id)."""
    id:         str
    type:       str = "Feature"
    geometry:   dict
    properties: dict


class MapEventsResponse(BaseModel):
    events: List[MapEventResponse]
    total:  int


# ─── Singleton engine (loaded once at startup) ────────────────────────────────
# Instantiating SeverityEngine is expensive (pre-computes anchor embeddings),
# so we create it once and reuse across requests.

_engine:    Optional[SeverityEngine]    = None
_extractor: Optional[EventNLPExtractor] = None


def _get_engine() -> SeverityEngine:
    global _engine
    if _engine is None:
        _engine = SeverityEngine(
            use_vertex=settings.use_vertex_embeddings,
            gcp_project=settings.gcp_project or None,
            gcp_location=settings.gcp_location,
            translate_non_english=settings.use_cloud_translate,
        )
    return _engine


def _get_extractor() -> EventNLPExtractor:
    global _extractor
    if _extractor is None:
        _extractor = EventNLPExtractor(
            use_gcp_nl=settings.use_gcp_nl_api,
            gcp_project=settings.gcp_project or None,
        )
    return _extractor


# ─── Demo / seed data ─────────────────────────────────────────────────────────
# Replace this with a real DB fetch once you have persistent storage.
# These mirror the smoke-test events in severity_engine.py so you can
# run the backend immediately and see markers on the map.

DEMO_EVENTS: List[EventSubmission] = [
    EventSubmission(
        id="evt-001",
        category="disaster_relief",
        document_texts=[
            "Flooding has submerged 3 villages. Over 2 000 families have lost their homes. "
            "Urgent rescue operations required immediately. People are stranded on rooftops "
            "without food or water. At least 12 deaths reported. Medical emergency declared."
        ],
        affected_population=10000,
        affected_area_km2=45.0,
        location_name="Assam, India",
        num_supporting_docs=3,
        reported_at=datetime.now(timezone.utc).isoformat(),
    ),
    EventSubmission(
        id="evt-002",
        category="water_and_sanitation",
        document_texts=[
            "The village has had no access to clean drinking water for 3 weeks. "
            "Cholera cases are rising — 45 confirmed, 3 deaths. Immediate intervention "
            "is critical. The only water source is contaminated. 800 people at risk."
        ],
        affected_population=800,
        location_name="Rural Maharashtra, India",
        num_supporting_docs=2,
        reported_at=datetime(2024, 6, 1, tzinfo=timezone.utc).isoformat(),
    ),
    EventSubmission(
        id="evt-003",
        category="food",
        document_texts=[
            "Severe acute malnutrition affecting 350 children under 5. "
            "Food stocks exhausted. Nearest distribution point 40 km away. "
            "3 deaths in the past week attributed to starvation."
        ],
        affected_population=1200,
        location_name="Rajasthan, India",
        num_supporting_docs=2,
        reported_at=datetime.now(timezone.utc).isoformat(),
    ),
    EventSubmission(
        id="evt-004",
        category="education",
        document_texts=[
            "We are planning an annual school supplies drive for the local community. "
            "The program runs every October and benefits around 200 children. "
            "Volunteers needed to sort and pack materials."
        ],
        affected_population=200,
        location_name="Bengaluru, India",
        num_supporting_docs=1,
        reported_at=datetime.now(timezone.utc).isoformat(),
    ),
    EventSubmission(
        id="evt-005",
        category="environment",
        document_texts=[
            "Illegal dumping of industrial waste near the river has destroyed 12 km of wetland. "
            "Fish populations collapsed. Drinking water for 5 000 residents at risk of contamination."
        ],
        affected_population=5000,
        affected_area_km2=12.0,
        location_name="Tamil Nadu, India",
        num_supporting_docs=2,
        reported_at=datetime.now(timezone.utc).isoformat(),
    ),
]


# ─── Helper: submission → scored map feature ──────────────────────────────────

def _submission_to_map_feature(submission: EventSubmission) -> MapEventResponse:
    """
    Run a single EventSubmission through the NLP + severity pipeline
    and return a MapEventResponse ready for the frontend.

    Note: coordinates are intentionally left as [None, None] here —
    the frontend (MapView.jsx) geocodes location_name via the
    Google Geocoding API.  This keeps GCP costs low (Geocoding API
    is called once per unique location, client-side, with caching).
    """
    engine    = _get_engine()
    extractor = _get_extractor()

    # Parse ISO date string if provided
    reported_at: Optional[datetime] = None
    if submission.reported_at:
        try:
            reported_at = datetime.fromisoformat(submission.reported_at)
        except ValueError:
            pass

    # Build EventInput for the severity engine
    event_input = EventInput(
        category            = submission.category,
        subtype             = submission.subtype,
        document_texts      = submission.document_texts,
        manager_context     = submission.manager_context,
        location_name       = submission.location_name,
        affected_population = submission.affected_population,
        affected_area_km2   = submission.affected_area_km2,
        num_supporting_docs = submission.num_supporting_docs,
        reported_at         = reported_at,
        language            = submission.language,
    )

    # Optionally enrich with NLP extraction (category suggestion, urgency)
    # Uncomment if you want to surface urgency_level from the extractor:
    # entities = extractor.extract(submission.document_texts)
    # if not submission.category and entities.suggested_category:
    #     event_input.category = entities.suggested_category

    result  = engine.score(event_input)
    feature = build_map_marker(event_input, result)

    event_id = submission.id or str(uuid.uuid4())

    return MapEventResponse(
        id         = event_id,
        type       = "Feature",
        geometry   = feature["geometry"],
        properties = feature["properties"],
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/map", response_model=MapEventsResponse, summary="Get all events for map view")
async def get_map_events():
    """
    Returns all active events scored and formatted for MapView.jsx.

    Currently uses DEMO_EVENTS — replace with a Firestore / DB query
    once you have persistent storage.

    The frontend will geocode `properties.location` → lat/lng using
    the Google Geocoding API (client-side, with a session cache).
    """
    try:
        features = [_submission_to_map_feature(ev) for ev in DEMO_EVENTS]
        return MapEventsResponse(events=features, total=len(features))
    except Exception as exc:
        logger.exception("Failed to score events for map: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/map/score", response_model=MapEventResponse, summary="Score a single new event")
async def score_event(submission: EventSubmission):
    """
    Score a single new event submission on demand and return its map feature.
    Useful for previewing severity before saving to the database.
    """
    try:
        return _submission_to_map_feature(submission)
    except Exception as exc:
        logger.exception("Failed to score event: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Standalone app (for direct uvicorn run) ──────────────────────────────────

app = FastAPI(title="Volunteer Matchmaker — Map API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "gcp_available": settings.gcp_available,
        "offline_mode":  settings.offline_mode,
    }


# ─── Run ──────────────────────────────────────────────────────────────────────
# uvicorn backend.api.map_routes:app --host 0.0.0.0 --port 8080 --reload

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.map_routes:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )