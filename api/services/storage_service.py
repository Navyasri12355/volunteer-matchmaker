"""Local filesystem storage service for certificate and event document uploads."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from api.core.config import settings
from api.models.document import DocumentUpload

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class StorageService:
    """Stores uploads on local disk and persists metadata in PostgreSQL."""

    def __init__(self, upload_root: str | None = None, max_upload_mb: int | None = None):
        self.upload_root = Path(upload_root or settings.local_upload_root).resolve()
        self.upload_root.mkdir(parents=True, exist_ok=True)
        self.max_upload_bytes = (max_upload_mb or settings.max_upload_mb) * 1024 * 1024

    async def upload_certificate(
        self,
        db: Session,
        volunteer_id: str,
        uploaded_by_uid: str,
        skill_key: str,
        file: UploadFile,
        certificate_id: str,
    ) -> DocumentUpload:
        """Save certificate file locally and insert metadata row."""
        return await self._save_upload(
            db=db,
            scope_type="certificate",
            scope_id=certificate_id,
            owner_folder=f"volunteers/{volunteer_id}/certificates/{skill_key}",
            uploaded_by_uid=uploaded_by_uid,
            file=file,
        )

    async def upload_event_documents(
        self,
        db: Session,
        ngo_id: str,
        event_id: str,
        uploaded_by_uid: str,
        files: list[UploadFile],
    ) -> list[DocumentUpload]:
        """Save event supporting documents locally and insert metadata rows."""
        uploads: list[DocumentUpload] = []
        for file in files:
            upload = await self._save_upload(
                db=db,
                scope_type="event",
                scope_id=event_id,
                owner_folder=f"ngos/{ngo_id}/events/{event_id}",
                uploaded_by_uid=uploaded_by_uid,
                file=file,
            )
            uploads.append(upload)
        return uploads

    async def upload_ngo_documents(
        self,
        db: Session,
        ngo_id: str,
        uploaded_by_uid: str,
        files: list[UploadFile],
    ) -> list[DocumentUpload]:
        """Save NGO-level supporting documents locally and insert metadata rows."""
        uploads: list[DocumentUpload] = []
        for file in files:
            upload = await self._save_upload(
                db=db,
                scope_type="ngo",
                scope_id=ngo_id,
                owner_folder=f"ngos/{ngo_id}/documents",
                uploaded_by_uid=uploaded_by_uid,
                file=file,
            )
            uploads.append(upload)
        return uploads

    async def get_signed_url(
        self,
        storage_path: str,
        expiration_hours: int = 24,
    ) -> str:
        """For local mode, return a pseudo URL/path placeholder."""
        _ = expiration_hours
        return storage_path

    async def delete_object(self, db: Session, document_id: str) -> bool:
        """Delete a local file and metadata record."""
        doc = db.query(DocumentUpload).filter(DocumentUpload.document_id == document_id).first()
        if not doc:
            return False

        try:
            file_path = Path(doc.storage_path)
            if file_path.exists():
                file_path.unlink()
        except OSError as exc:
            logger.warning("Failed to delete local upload %s: %s", doc.storage_path, exc)

        db.delete(doc)
        return True

    async def _save_upload(
        self,
        db: Session,
        scope_type: str,
        scope_id: str,
        owner_folder: str,
        uploaded_by_uid: str,
        file: UploadFile,
    ) -> DocumentUpload:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
        if len(content) > self.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max allowed size is {settings.max_upload_mb} MB",
            )

        document_id = f"doc_{uuid4().hex}"
        original_name = file.filename or "upload.bin"
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF and DOCX files are allowed")
        if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file content type")
        safe_name = f"{uuid4().hex}_{Path(original_name).name}"

        target_dir = self.upload_root / owner_folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / safe_name
        target_file.write_bytes(content)

        document = DocumentUpload(
            document_id=document_id,
            scope_type=scope_type,
            scope_id=scope_id,
            file_name=original_name,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            storage_path=str(target_file),
            uploaded_by_uid=uploaded_by_uid,
        )
        db.add(document)
        return document
