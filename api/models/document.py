"""Document metadata model for locally stored uploads."""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.sql import func

from api.db.session import Base


class DocumentUpload(Base):
    __tablename__ = "document_uploads"

    document_id = Column(String, primary_key=True, index=True)
    scope_type = Column(String, nullable=False, index=True)  # event | certificate
    scope_id = Column(String, nullable=False, index=True)    # event_id | certificate_id

    file_name = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)

    storage_path = Column(String, nullable=False)  # local filesystem path
    uploaded_by_uid = Column(String, ForeignKey("users.firebase_uid"), nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
