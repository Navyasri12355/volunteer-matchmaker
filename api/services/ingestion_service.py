"""
Ingestion service — orchestrates document loading and processing.
"""

import logging
from typing import List, Tuple
from pathlib import Path

from backend.ingestion.ingestor_to_severity import ingest_and_score
from backend.nlp.severity_engine import SeverityEngine

logger = logging.getLogger(__name__)


class IngestionService:
    """Wraps backend.ingestion and backend.nlp for the API layer."""

    def __init__(self, engine: SeverityEngine):
        self.engine = engine

    async def process_event_documents(
        self,
        filepaths: List[str],
        category: str,
        location_name: str = "",
        affected_population: int = None,
        affected_area_km2: float = None,
        reported_at = None,
        language: str = None,
        manager_context: str = "",
        subtype: str = None,
    ) -> Tuple[dict, dict]:
        """
        Process uploaded event documents and return severity result + map marker.

        Args:
            filepaths: List of uploaded file paths (local temp paths after Firebase Storage retrieval).
            category: Event category (must be valid).
            location_name: Human-readable location.
            affected_population: Estimated affected population.
            affected_area_km2: Affected area in km².
            reported_at: When the event was reported (datetime).
            language: ISO 639-1 language code.
            manager_context: Free-text NGO manager description.
            subtype: Custom subtype (if allowed for category).

        Returns:
            (severity_result_dict, map_marker_dict)
        """
        try:
            result, marker = ingest_and_score(
                filepaths=filepaths,
                category=category,
                engine=self.engine,
                subtype=subtype,
                location_name=location_name,
                affected_population=affected_population,
                affected_area_km2=affected_area_km2,
                reported_at=reported_at,
                language=language,
                manager_context=manager_context,
            )

            # Convert to dict for storage
            result_dict = {
                "score": result.score,
                "band": result.band.value,
                "map_color": result.map_color,
                "breakdown": result.breakdown,
                "top_evidence": result.top_evidence,
                "warnings": result.warnings,
            }

            return result_dict, marker

        except Exception as exc:
            logger.error("Document ingestion failed: %s", exc)
            raise
