"""
NGO manager routes.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from api.deps import get_db, get_current_ngo_manager
from api.schemas.ngo import NGOProfileResponse
from api.models.ngo import NGO
from api.models.user import User
from api.models.document import DocumentUpload
from api.services.storage_service import StorageService
from api.services.pipeline_service import process_ngo_upload_pipeline

router = APIRouter()
storage_service = StorageService()


@router.get("/me", response_model=NGOProfileResponse)
async def get_ngo_profile(
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """Get the current NGO's profile and trust score."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ngo = db.query(NGO).filter(NGO.firebase_uid == user.firebase_uid).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO profile not found")

    return NGOProfileResponse(
        ngo_id=ngo.ngo_id,
        org_name=ngo.org_name,
        org_registration_number=ngo.org_registration_number,
        allowed_categories=ngo.allowed_categories or [],
        custom_subtypes=ngo.custom_subtypes or {},
        trust_score=ngo.trust_score,
        is_verified=ngo.is_verified,
        is_suspended=ngo.is_suspended,
        email=user.email,
    )


@router.get("/{ngo_id}", response_model=NGOProfileResponse)
async def get_ngo_by_id(
    ngo_id: str,
    db: Session = Depends(get_db),
):
    """Get an NGO's public profile (verification status, name)."""
    ngo = db.query(NGO).filter(NGO.ngo_id == ngo_id).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    return NGOProfileResponse.from_orm(ngo)

@router.post("/{ngo_id}/documents")
async def upload_ngo_document(
    ngo_id: str,
    files: list[UploadFile] = File(..., alias="files[]"),
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """Upload verification documents for an NGO."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ngo = db.query(NGO).filter(NGO.firebase_uid == user.firebase_uid).first()
    if not ngo or ngo.ngo_id != ngo_id:
        raise HTTPException(status_code=403, detail="Not authorized or NGO not found")

    uploads = await storage_service.upload_ngo_documents(
        db=db,
        ngo_id=ngo.ngo_id,
        uploaded_by_uid=user.firebase_uid,
        files=files,
    )
    db.flush()

    filepaths = [upload.storage_path for upload in uploads]
    pipeline_summary = await process_ngo_upload_pipeline(db, ngo.ngo_id, filepaths)

    db.commit()

    return {"message": "Documents uploaded successfully", "count": len(uploads), "pipeline": pipeline_summary}


@router.get("/{ngo_id}/documents")
async def list_ngo_documents(
    ngo_id: str,
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """List NGO-owned uploaded documents."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ngo = db.query(NGO).filter(NGO.firebase_uid == user.firebase_uid).first()
    if not ngo or ngo.ngo_id != ngo_id:
        raise HTTPException(status_code=403, detail="Not authorized or NGO not found")

    docs = db.query(DocumentUpload).filter(DocumentUpload.scope_type == "ngo", DocumentUpload.scope_id == ngo_id).all()
    return {
        "ngo_id": ngo_id,
        "documents": [
            {
                "document_id": doc.document_id,
                "file_name": doc.file_name,
                "content_type": doc.content_type,
                "size_bytes": doc.size_bytes,
                "created_at": doc.created_at,
            }
            for doc in docs
        ],
    }


@router.get("/documents/{document_id}/download")
async def download_ngo_document(
    document_id: str,
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """Download an NGO-level uploaded document."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ngo = db.query(NGO).filter(NGO.firebase_uid == user.firebase_uid).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    doc = db.query(DocumentUpload).filter(DocumentUpload.document_id == document_id, DocumentUpload.scope_type == "ngo").first()
    if not doc or doc.scope_id != ngo.ngo_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this document")

    file_path = Path(doc.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file not found on disk")

    return FileResponse(path=str(file_path), media_type=doc.content_type, filename=doc.file_name)


@router.delete("/documents/{document_id}")
async def delete_ngo_document(
    document_id: str,
    current_user: dict = Depends(get_current_ngo_manager),
    db: Session = Depends(get_db),
):
    """Delete an NGO document and its stored file."""
    user = db.query(User).filter(User.firebase_uid == current_user["uid"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ngo = db.query(NGO).filter(NGO.firebase_uid == user.firebase_uid).first()
    if not ngo:
        raise HTTPException(status_code=404, detail="NGO not found")

    doc = db.query(DocumentUpload).filter(DocumentUpload.document_id == document_id, DocumentUpload.scope_type == "ngo").first()
    if not doc or doc.scope_id != ngo.ngo_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")

    deleted = await storage_service.delete_object(db, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    db.commit()
    return {"message": "Document deleted successfully", "document_id": document_id}

