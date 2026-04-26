"""
nlp
---
Public API for the NLP package.

All external callers (API routers, event_service, etc.) should import
from here.  Internal modules may import from each other directly.

    from backend.nlp import SeverityEngine, EventInput, SeverityResult
    from backend.nlp import CategoryConfig, CATEGORIES
    from backend.nlp import EventNLPExtractor, ExtractedEntities
    from backend.nlp import TrustScorer, SkillVerifier
"""

from nlp.category_config import CategoryConfig, EventCategory, CATEGORIES
from nlp.severity_engine import (
    SeverityEngine,
    EventInput,
    SeverityResult,
    SeverityBand,
    build_map_marker,
)
from nlp.event_nlp_extractor import EventNLPExtractor, ExtractedEntities
from nlp.trust_scorer import TrustScorer, NGOTrustScore, VolunteerPointsLedger
from nlp.skill_verifier import SkillVerifier, CertificateVerificationResult

__all__ = [
    # config
    "CategoryConfig",
    "EventCategory",
    "CATEGORIES",
    # severity
    "SeverityEngine",
    "EventInput",
    "SeverityResult",
    "SeverityBand",
    "build_map_marker",
    # extractor
    "EventNLPExtractor",
    "ExtractedEntities",
    # trust
    "TrustScorer",
    "NGOTrustScore",
    "VolunteerPointsLedger",
    # skills
    "SkillVerifier",
    "CertificateVerificationResult",
]
