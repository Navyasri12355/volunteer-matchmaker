"""
ingestion
---------
Public API for the document ingestion package.

Import from here rather than from individual modules so that internal
refactors don't break callers.

    from backend.ingestion import load_document, chunk_documents, ingest_directory
"""

from backend.ingestion.ingestor import (
    load_document,
    load_pdf,
    load_markdown,
    load_docx,
    load_txt,
    chunk_documents,
    ingest_directory,
    LOADERS,
)

__all__ = [
    "load_document",
    "load_pdf",
    "load_markdown",
    "load_docx",
    "load_txt",
    "chunk_documents",
    "ingest_directory",
    "LOADERS",
]