"""
Event routes — creation, listing, detail.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pathlib import Path

from api.deps import get_db, get_current_ngo_manager
from api.schemas.event import CreateEventRequest, EventResponse, EventListResponse
from api.models.document import DocumentUpload
from api.models.event import Event, SeverityBand
from api.models.ngo import NGO
from api.models.user import User
from api.services.storage_service import StorageService
from api.services.pipeline_service import process_event_upload_pipeline
from api.services.trust_service import TrustService

router = APIRouter()
storage_service = StorageService()


@router.post("", response_model=EventResponse)
async def create_event(
    req: CreateEventRequest,
    files: list[UploadFile] = File(default=None, alias="files[]"),
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """
    Create a new event. Uses document ingestion, NLP extraction, matching,
    and trust gating before persisting the final score.
    """
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ngo = db.query(NGO).filter(NGO.firebase_uid == user.firebase_uid).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    trust_service = TrustService()
    allowed, reason = await trust_service.check_ngo_can_create_event(db, ngo.ngo_id)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=reason,
        )

    event_id = f"evt_{int(datetime.now(timezone.utc).timestamp())}"
    event = Event(
        event_id=event_id,
        ngo_id=ngo.ngo_id,
        title=req.title,
        category=req.category,
        subtype=req.subtype,
        location_name=req.location_name,
        lat=req.lat,
        lng=req.lng,
        affected_population=req.affected_population,
        affected_area_km2=req.affected_area_km2,
        severity_score=0.0,
        severity_band=SeverityBand.LOW,
        map_color="#718096",
        num_volunteers_needed=req.num_volunteers_needed,
        num_volunteers_assigned=0,
        manager_context=req.manager_context,
        reported_at=req.reported_at or datetime.now(timezone.utc),
        tags=["active"],
    )

    db.add(event)
    db.flush()

    uploads = []

    if files:
        uploads = await storage_service.upload_event_documents(
            db=db,
            ngo_id=ngo.ngo_id,
            event_id=event.event_id,
            uploaded_by_uid=user.firebase_uid,
            files=files,
        )

    pipeline_summary = await process_event_upload_pipeline(
        db=db,
        event_id=event.event_id,
        ngo_id=ngo.ngo_id,
        category=req.category,
        location_name=req.location_name,
        lat=req.lat,
        lng=req.lng,
        affected_population=req.affected_population,
        affected_area_km2=req.affected_area_km2,
        severity_band=event.severity_band.value if hasattr(event.severity_band, "value") else str(event.severity_band),
        filepaths=[upload.storage_path for upload in uploads],
    )

    severity = pipeline_summary.get("severity") or {}
    if severity:
        event.severity_score = severity.get("score", event.severity_score)
        severity_band_value = severity.get("band", event.severity_band)
        event.severity_band = SeverityBand(severity_band_value) if not isinstance(severity_band_value, SeverityBand) else severity_band_value
        event.map_color = severity.get("map_color", event.map_color)
        event.top_evidence = severity.get("top_evidence", event.top_evidence)
        event.breakdown = severity.get("breakdown", event.breakdown)

    if pipeline_summary.get("entities"):
        event.tags = ["active", "nlp-extracted"]

    db.commit()

    return EventResponse.from_orm(event)


@router.post("/{event_id}/documents")
async def upload_event_documents(
    event_id: str,
    files: list[UploadFile] = File(..., alias="files[]"),
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """Upload supporting documents for an existing event (local storage mode)."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ngo = db.query(NGO).filter(NGO.firebase_uid == user.firebase_uid).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    event = db.query(Event).filter(Event.event_id == event_id, Event.ngo_id == ngo.ngo_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    uploads = await storage_service.upload_event_documents(
        db=db,
        ngo_id=ngo.ngo_id,
        event_id=event.event_id,
        uploaded_by_uid=user.firebase_uid,
        files=files,
    )
    db.commit()

    pipeline_summary = await process_event_upload_pipeline(
        db=db,
        event_id=event.event_id,
        ngo_id=ngo.ngo_id,
        category=event.category,
        location_name=event.location_name,
        lat=event.lat,
        lng=event.lng,
        affected_population=event.affected_population,
        affected_area_km2=event.affected_area_km2,
        severity_band=event.severity_band.value if hasattr(event.severity_band, "value") else str(event.severity_band),
        filepaths=[u.storage_path for u in uploads],
    )

    return {
        "event_id": event_id,
        "pipeline": pipeline_summary,
        "uploaded_documents": [
            {
                "document_id": upload.document_id,
                "file_name": upload.file_name,
                "storage_path": upload.storage_path,
                "size_bytes": upload.size_bytes,
                "content_type": upload.content_type,
            }
            for upload in uploads
        ],
    }


@router.get("/{event_id}/documents")
async def list_event_documents(
    event_id: str,
    db: Session = Depends(get_db),
):
    """List metadata of uploaded event documents."""
    docs = db.query(DocumentUpload).filter(DocumentUpload.scope_type == "event", DocumentUpload.scope_id == event_id).all()
    return {
        "event_id": event_id,
        "documents": [
            {
                "document_id": doc.document_id,
                "file_name": doc.file_name,
                "storage_path": doc.storage_path,
                "size_bytes": doc.size_bytes,
                "content_type": doc.content_type,
                "uploaded_by_uid": doc.uploaded_by_uid,
                "created_at": doc.created_at,
            }
            for doc in docs
        ],
    }


@router.get("/documents/{document_id}/download")
async def download_event_document(
    document_id: str,
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """Download a locally stored event document by document ID."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ngo = db.query(NGO).filter(NGO.firebase_uid == user.firebase_uid).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    doc = db.query(DocumentUpload).filter(DocumentUpload.document_id == document_id, DocumentUpload.scope_type == "event").first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    event = db.query(Event).filter(Event.event_id == doc.scope_id).first()
    if not event or event.ngo_id != ngo.ngo_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this document")

    file_path = Path(doc.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found on disk")

    return FileResponse(path=str(file_path), media_type=doc.content_type, filename=doc.file_name)


@router.get("", response_model=EventListResponse)
async def list_events(
    category: str = Query(None),
    band: str = Query(None),
    lat: float = Query(None),
    lng: float = Query(None),
    radius_km: float = Query(None),
    limit: int = Query(50, le=200),
    cursor: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    List all events (public endpoint). Supports filtering and pagination.
    
    TODO: Implement geographic filtering if lat/lng/radius provided.
    """
    query = db.query(Event).filter(Event.tags.contains(["active"]))

    if category:
        query = query.filter(Event.category == category)
    if band:
        query = query.filter(Event.severity_band == band)

    events = query.limit(limit).all()
    return EventListResponse(
        events=[EventResponse.from_orm(e) for e in events],
        next_cursor=None,  # TODO: Implement cursor-based pagination
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event_detail(
    event_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed event information including evidence and volunteers needed."""
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return EventResponse.from_orm(event)


@router.patch("/{event_id}")
async def update_event(
    event_id: str,
    tags: list[str] = None,
    num_volunteers_needed: int = None,
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """Update event status, tags, or volunteer count (NGO manager or admin only)."""
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # TODO: Check user is the NGO manager who created this event
    if tags is not None:
        event.tags = tags
    if num_volunteers_needed is not None:
        event.num_volunteers_needed = num_volunteers_needed

    db.commit()
    return EventResponse.from_orm(event)
