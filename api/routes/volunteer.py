"""
Volunteer routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from uuid import uuid4
from pathlib import Path

from api.deps import get_db, get_current_volunteer
from api.schemas.volunteer import VolunteerProfileResponse, SkillCertificateResponse
from api.models.volunteer import Volunteer
from api.models.user import User
from api.models.skill import SkillCertificate, SkillVerificationStatus
from api.models.document import DocumentUpload
from api.services.storage_service import StorageService
from api.services.pipeline_service import process_volunteer_upload_pipeline

router = APIRouter()
storage_service = StorageService()

@router.get("/me", response_model=VolunteerProfileResponse)
async def get_volunteer_profile(
    current_user: dict = Depends(get_current_volunteer),
    db: Session = Depends(get_db),
):
    """Get the current volunteer's profile."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    volunteer = db.query(Volunteer).filter(Volunteer.firebase_uid == user.firebase_uid).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer profile not found")

    return VolunteerProfileResponse(
        volunteer_id=volunteer.volunteer_id,
        full_name=volunteer.full_name,
        email=user.email,
        phone=volunteer.phone,
        age=volunteer.age,
        city=volunteer.city,
        state=volunteer.state,
        lat=volunteer.lat,
        lng=volunteer.lng,
        willing_to_travel_km=volunteer.willing_to_travel_km,
        skills=volunteer.skills or [],
        preferred_categories=volunteer.preferred_categories or [],
        total_points=volunteer.total_points,
        reliability_score=volunteer.reliability_score,
    )


@router.post("/certificates")
async def upload_certificate(
    skill_key: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_volunteer),
    db: Session = Depends(get_db),
):
    """
    Upload a skill certificate for verification.
    """
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    volunteer = db.query(Volunteer).filter(Volunteer.firebase_uid == user.firebase_uid).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer profile not found")

    certificate_id = f"cert_{uuid4().hex}"
    upload = await storage_service.upload_certificate(
        db=db,
        volunteer_id=volunteer.volunteer_id,
        uploaded_by_uid=user.firebase_uid,
        skill_key=skill_key,
        file=file,
        certificate_id=certificate_id,
    )

    certificate = SkillCertificate(
        certificate_id=certificate_id,
        volunteer_id=volunteer.volunteer_id,
        skill_key=skill_key,
        status=SkillVerificationStatus.PENDING_REVIEW,
        storage_path=upload.storage_path,
        requires_manual=True,
    )
    db.add(certificate)
    db.flush()

    pipeline_summary = await process_volunteer_upload_pipeline(
        db=db,
        volunteer_id=volunteer.volunteer_id,
        skill_key=skill_key,
        filepaths=[upload.storage_path],
    )

    db.commit()

    return {
        "message": "Skill certificate uploaded successfully",
        "certificate": SkillCertificateResponse(
            skill_key=certificate.skill_key,
            status=certificate.status.value if hasattr(certificate.status, "value") else str(certificate.status),
            issue_date=certificate.issue_date.isoformat() if certificate.issue_date else None,
            expiry_date=certificate.expiry_date.isoformat() if certificate.expiry_date else None,
            requires_manual=bool(certificate.requires_manual),
        ),
        "pipeline": pipeline_summary,
    }


@router.get("/documents/{document_id}/download")
async def download_my_certificate_document(
    document_id: str,
    current_user: dict = Depends(get_current_volunteer),
    db: Session = Depends(get_db),
):
    """Download a locally stored certificate document owned by the current volunteer."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    volunteer = db.query(Volunteer).filter(Volunteer.firebase_uid == user.firebase_uid).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer profile not found")

    doc = db.query(DocumentUpload).filter(DocumentUpload.document_id == document_id, DocumentUpload.scope_type == "certificate").first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    certificate = db.query(SkillCertificate).filter(SkillCertificate.certificate_id == doc.scope_id).first()
    if not certificate or certificate.volunteer_id != volunteer.volunteer_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this document")

    file_path = Path(doc.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found on disk")

    return FileResponse(path=str(file_path), media_type=doc.content_type, filename=doc.file_name)


@router.get("/documents")
async def list_my_certificate_documents(
    current_user: dict = Depends(get_current_volunteer),
    db: Session = Depends(get_db),
):
    """List current volunteer certificate documents and metadata."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    volunteer = db.query(Volunteer).filter(Volunteer.firebase_uid == user.firebase_uid).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer profile not found")

    certificates = db.query(SkillCertificate).filter(SkillCertificate.volunteer_id == volunteer.volunteer_id).all()
    cert_ids = [c.certificate_id for c in certificates]
    if not cert_ids:
        return {"documents": []}

    docs = (
        db.query(DocumentUpload)
        .filter(DocumentUpload.scope_type == "certificate", DocumentUpload.scope_id.in_(cert_ids))
        .all()
    )

    certificate_by_id = {c.certificate_id: c for c in certificates}
    return {
        "documents": [
            {
                "document_id": d.document_id,
                "certificate_id": d.scope_id,
                "skill_key": certificate_by_id[d.scope_id].skill_key if d.scope_id in certificate_by_id else None,
                "status": (
                    certificate_by_id[d.scope_id].status.value
                    if d.scope_id in certificate_by_id and hasattr(certificate_by_id[d.scope_id].status, "value")
                    else str(certificate_by_id[d.scope_id].status) if d.scope_id in certificate_by_id else None
                ),
                "file_name": d.file_name,
                "content_type": d.content_type,
                "size_bytes": d.size_bytes,
                "created_at": d.created_at,
            }
            for d in docs
        ]
    }


@router.delete("/documents/{document_id}")
async def delete_my_certificate_document(
    document_id: str,
    current_user: dict = Depends(get_current_volunteer),
    db: Session = Depends(get_db),
):
    """Delete a volunteer certificate document and its certificate row."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    volunteer = db.query(Volunteer).filter(Volunteer.firebase_uid == user.firebase_uid).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer profile not found")

    doc = db.query(DocumentUpload).filter(DocumentUpload.document_id == document_id, DocumentUpload.scope_type == "certificate").first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    certificate = db.query(SkillCertificate).filter(SkillCertificate.certificate_id == doc.scope_id).first()
    if not certificate or certificate.volunteer_id != volunteer.volunteer_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")

    deleted = await storage_service.delete_object(db, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    db.delete(certificate)
    db.commit()
    return {"message": "Document deleted successfully", "document_id": document_id}


@router.get("/{volunteer_id}", response_model=VolunteerProfileResponse)
async def get_volunteer_public_profile(
    volunteer_id: str,
    db: Session = Depends(get_db),
):
    """Get a volunteer's public profile (points, skills, availability)."""
    volunteer = db.query(Volunteer).filter(Volunteer.volunteer_id == volunteer_id).first()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    user = db.query(User).filter(User.firebase_uid == volunteer.firebase_uid).first()
    return VolunteerProfileResponse(
        volunteer_id=volunteer.volunteer_id,
        full_name=volunteer.full_name,
        email=user.email if user else "",
        phone=volunteer.phone,
        age=volunteer.age,
        city=volunteer.city,
        state=volunteer.state,
        lat=volunteer.lat,
        lng=volunteer.lng,
        willing_to_travel_km=volunteer.willing_to_travel_km,
        skills=volunteer.skills or [],
        preferred_categories=volunteer.preferred_categories or [],
        total_points=volunteer.total_points,
        reliability_score=volunteer.reliability_score,
    )
