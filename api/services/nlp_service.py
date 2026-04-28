"""
NLP service — orchestrates extraction, scoring, and entity analysis.
"""

import logging
from backend.nlp.severity_engine import SeverityEngine, EventInput
from backend.nlp.event_nlp_extractor import EventNLPExtractor

logger = logging.getLogger(__name__)


class NLPService:
    """Wraps backend.nlp modules for the API layer."""

    def __init__(self, severity_engine: SeverityEngine, extractor: EventNLPExtractor):
        self.engine = severity_engine
        self.extractor = extractor

    async def extract_entities(self, texts: list[str]) -> dict:
        """
        Extract structured information from event document texts.

        Returns:
            {
                "affected_population": int,
                "locations": [str],
                "urgency_level": str,
                "suggested_category": str,
                "detected_language": str,
                ...
            }
        """
        try:
            entities = self.extractor.extract(texts)
            return {
                "affected_population": entities.affected_population,
                "locations": entities.locations,
                "urgency_level": entities.urgency_level,
                "suggested_category": entities.suggested_category,
                "detected_language": entities.detected_language,
                "extraction_method": entities.extraction_method,
            }
        except Exception as exc:
            logger.error("Entity extraction failed: %s", exc)
            raise

    async def compute_severity(
        self,
        texts: list[str],
        category: str,
        affected_population: int = None,
        affected_area_km2: float = None,
        reported_at = None,
        num_docs: int = 1,
    ) -> dict:
        """
        Compute composite severity score for an event.

        Returns:
            {
                "score": float,
                "band": str,
                "map_color": str,
                "breakdown": dict,
                "top_evidence": [str],
                ...
            }
        """
        try:
            event = EventInput(
                category=category,
                document_texts=texts,
                affected_population=affected_population,
                affected_area_km2=affected_area_km2,
                reported_at=reported_at,
                num_supporting_docs=num_docs,
            )
            result = self.engine.score(event)

            return {
                "score": result.score,
                "band": result.band.value,
                "map_color": result.map_color,
                "breakdown": result.breakdown,
                "top_evidence": result.top_evidence,
                "warnings": result.warnings,
            }
        except Exception as exc:
            logger.error("Severity scoring failed: %s", exc)
            raise
