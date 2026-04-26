"""
ingestor_to_severity.py
-----------------------
Bridges the Document Ingestor (ingestor.py) and the SeverityEngine.

Typical call flow
~~~~~~~~~~~~~~~~~
    NGO manager uploads docs  →  ingest_and_score()  →  SeverityResult

The function:
  1. Runs the ingestor pipeline on the uploaded file(s).
  2. Reconstructs per-page/per-doc text blocks.
  3. Feeds them into SeverityEngine.score().
  4. Returns the result + a Leaflet-compatible map marker dict.

Usage
~~~~~
    from ingestor_to_severity import ingest_and_score

    result, marker = ingest_and_score(
        filepaths=["report.pdf", "survey.docx"],
        category="water_and_sanitation",
        location_name="Rural Odisha, India",
        affected_population=3500,
        reported_at=datetime(2025, 3, 15, tzinfo=timezone.utc),
        engine=engine,    # pass a shared SeverityEngine instance
    )
    print(result.score, result.band)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ingestor import load_document, chunk_documents
from severity_engine import EventInput, SeverityEngine, SeverityResult, build_map_marker


def ingest_and_score(
    filepaths: List[str],
    category: str,
    engine: SeverityEngine,
    *,
    subtype: Optional[str]         = None,
    location_name: str             = "",
    affected_population: Optional[int]   = None,
    affected_area_km2: Optional[float]   = None,
    reported_at: Optional[datetime]      = None,
    language: Optional[str]              = None,
    manager_context: str                 = "",
    chunk_size: int                      = 500,
    chunk_overlap: int                   = 50,
) -> tuple[SeverityResult, dict]:
    """
    End-to-end: ingest files → build EventInput → score → return result + marker.

    Parameters
    ----------
    filepaths          : List of file paths (PDF, DOCX, MD, TXT).
    category           : Event category string (must match CATEGORY_WEIGHTS keys).
    engine             : A pre-initialised SeverityEngine instance.
    subtype            : Optional subtype / custom label.
    location_name      : Human-readable location string (for display; geocoding
                         is the caller's responsibility).
    affected_population: Estimated number of people affected.
    affected_area_km2  : Estimated geographic area in km².
    reported_at        : When the need was first reported (tz-aware datetime).
    language           : ISO 639-1 code of the documents; None → assume English.
    manager_context    : Free-text description from the NGO manager.
    chunk_size / chunk_overlap : Passed through to the ingestor chunker.

    Returns
    -------
    (SeverityResult, map_marker_dict)
    """
    all_texts: List[str] = []
    num_docs = len(filepaths)

    for fp in filepaths:
        try:
            raw_docs = load_document(fp)
            chunks   = chunk_documents(raw_docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            # Reconstruct contiguous text per original document
            # (better for semantic coherence than using tiny chunks directly)
            page_texts: dict[int, list[str]] = {}
            for chunk in chunks:
                page = chunk["metadata"].get("page", 1)
                page_texts.setdefault(page, []).append(chunk["content"])
            for page_content in page_texts.values():
                all_texts.append(" ".join(page_content))
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to ingest %s: %s", Path(fp).name, exc)

    event = EventInput(
        category=category,
        subtype=subtype,
        document_texts=all_texts,
        affected_population=affected_population,
        affected_area_km2=affected_area_km2,
        location_name=location_name,
        reported_at=reported_at or datetime.now(timezone.utc),
        language=language,
        num_supporting_docs=num_docs,
        manager_context=manager_context,
    )

    result = engine.score(event)
    marker = build_map_marker(event, result)
    return result, marker
