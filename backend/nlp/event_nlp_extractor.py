"""
event_nlp_extractor.py
----------------------
Extracts structured information from raw document text submitted with an event.

What it pulls out
~~~~~~~~~~~~~~~~~
- Affected population estimate  (numbers near "people", "families", "villages", …)
- Mentioned locations            (city / district / state names)
- Urgency signals                (words/phrases implying immediacy)
- Key quantitative claims        (death tolls, case counts, area in km²)
- Suggested category / subtype   (best-guess label if the NGO didn't set one)
- Language detection             (ISO 639-1 code)

Google Cloud services used
~~~~~~~~~~~~~~~~~~~~~~~~~~
- **Cloud Natural Language API** (v1) — entity extraction, sentiment, syntax.
  Free tier: 5 000 units/month (each doc = 1 unit).  Well within credits.
  Falls back to a regex + keyword approach when credentials are absent.

Usage
~~~~~
    extractor = EventNLPExtractor()
    entities  = extractor.extract(texts=["Flood hit 3 villages near Bhubaneswar…"])
    print(entities.affected_population, entities.locations, entities.urgency_level)
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Urgency keyword tiers
# ---------------------------------------------------------------------------

URGENCY_HIGH: List[str] = [
    "immediate", "urgent", "emergency", "critical", "life-threatening",
    "mass casualty", "deaths", "died", "killed", "stranded", "no access",
    "outbreak", "epidemic", "collapsed", "destroyed", "submerged", "evacuate",
]
URGENCY_MED: List[str] = [
    "shortage", "lack", "insufficient", "at risk", "deteriorating",
    "displaced", "homeless", "contaminated", "unsafe", "severe",
]
URGENCY_LOW: List[str] = [
    "awareness", "workshop", "training", "annual", "routine", "planned",
    "scheduled", "ongoing program", "gradual", "long-term",
]

# Patterns to pull numbers linked to population-scale nouns
_POP_PATTERN = re.compile(
    r"(\d[\d,]*)\s*(?:people|persons|individuals|families|households|"
    r"children|residents|villagers|survivors|victims|refugees|displaced)",
    re.IGNORECASE,
)
_DEATH_PATTERN = re.compile(
    r"(\d[\d,]*)\s*(?:deaths?|dead|killed|casualties|fatalities)",
    re.IGNORECASE,
)
_AREA_PATTERN = re.compile(
    r"(\d[\d,.]*)\s*(?:km²|km2|square\s*km|sq\.?\s*km)",
    re.IGNORECASE,
)
_CASE_PATTERN = re.compile(
    r"(\d[\d,]*)\s*(?:cases?|confirmed\s*cases?|infections?|patients?)",
    re.IGNORECASE,
)

# Simple category hint keywords (used in fallback / to supplement GCP NL)
_CATEGORY_HINTS: Dict[str, List[str]] = {
    "disaster_relief":       ["flood", "earthquake", "cyclone", "landslide", "rescue", "evacuation", "disaster"],
    "water_and_sanitation":  ["water", "sanitation", "cholera", "well", "borehole", "wash", "hygiene", "sewage"],
    "food":                  ["food", "hunger", "malnutrition", "starvation", "famine", "meal", "nutrition"],
    "education":             ["school", "education", "literacy", "student", "teacher", "classroom", "tutor"],
    "environment":           ["forest", "tree", "pollution", "waste", "beach", "river", "habitat", "biodiversity"],
    "animal_welfare":        ["animal", "stray", "poaching", "veterinary", "rescue", "wildlife", "pet"],
}


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class ExtractedEntities:
    # Population / scale
    affected_population: Optional[int]   = None   # best single estimate
    population_mentions: List[int]       = field(default_factory=list)
    death_count:         Optional[int]   = None
    case_count:          Optional[int]   = None
    area_km2:            Optional[float] = None

    # Geography
    locations: List[str] = field(default_factory=list)  # de-duped, title-cased

    # Urgency
    urgency_level:   str        = "low"    # "high" | "medium" | "low"
    urgency_signals: List[str]  = field(default_factory=list)

    # Category hints (for UI pre-fill / validation assist)
    suggested_category: Optional[str] = None
    category_scores:    Dict[str, int] = field(default_factory=dict)

    # Language
    detected_language: str = "en"  # ISO 639-1

    # Raw GCP entities (if available)
    gcp_entities: List[dict] = field(default_factory=list)

    # Extraction method used (for audit)
    extraction_method: str = "regex"  # "gcp_nl" | "regex"


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class EventNLPExtractor:
    """
    Extracts structured entities from event document text.

    Parameters
    ----------
    use_gcp_nl : bool
        Attempt to use Google Cloud Natural Language API.  Falls back to
        regex heuristics if credentials are absent or on error.
    gcp_project : str | None
        GCP project ID (reads GCP_PROJECT env var if None).
    """

    def __init__(
        self,
        use_gcp_nl: bool = True,
        gcp_project: Optional[str] = None,
    ):
        self._project   = gcp_project or os.getenv("GCP_PROJECT", "")
        self._nl_client = self._init_nl_client(use_gcp_nl)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, texts: List[str]) -> ExtractedEntities:
        """
        Run extraction over a list of text strings (e.g. document chunks).
        Returns a merged ExtractedEntities result.
        """
        combined = "\n\n".join(t for t in texts if t.strip())
        if not combined:
            return ExtractedEntities()

        if self._nl_client:
            try:
                return self._extract_gcp(combined)
            except Exception as exc:
                logger.warning("GCP NL extraction failed (%s) – falling back to regex.", exc)

        return self._extract_regex(combined)

    # ------------------------------------------------------------------
    # GCP Natural Language API path
    # ------------------------------------------------------------------

    def _init_nl_client(self, use_gcp_nl: bool):
        if not use_gcp_nl or not self._project:
            return None
        try:
            from google.cloud import language_v1  # type: ignore
            client = language_v1.LanguageServiceClient()
            logger.info("Google Cloud Natural Language API client initialised.")
            return client
        except Exception as exc:
            logger.info("GCP NL client not available (%s) – using regex fallback.", exc)
            return None

    def _extract_gcp(self, text: str) -> ExtractedEntities:
        from google.cloud import language_v1  # type: ignore

        document = language_v1.Document(
            content=text[:100_000],          # API limit: 1M chars, we cap at 100k
            type_=language_v1.Document.Type.PLAIN_TEXT,
        )

        # Entity analysis
        entity_response = self._nl_client.analyze_entities(
            request={"document": document, "encoding_type": language_v1.EncodingType.UTF8}
        )

        locations:    List[str]  = []
        gcp_entities: List[dict] = []

        for entity in entity_response.entities:
            gcp_entities.append({
                "name":     entity.name,
                "type":     entity.type_.name,
                "salience": round(entity.salience, 4),
            })
            if entity.type_.name == "LOCATION":
                loc = entity.name.strip().title()
                if loc and loc not in locations:
                    locations.append(loc)

        # Language detection from the entity response metadata (if available)
        detected_lang = "en"
        try:
            lang_response = self._nl_client.analyze_sentiment(
                request={"document": document}
            )
            detected_lang = lang_response.language or "en"
        except Exception:
            pass

        # Merge with regex for numeric fields (GCP NL doesn't parse numbers)
        regex_result = self._extract_regex(text)

        return ExtractedEntities(
            affected_population  = regex_result.affected_population,
            population_mentions  = regex_result.population_mentions,
            death_count          = regex_result.death_count,
            case_count           = regex_result.case_count,
            area_km2             = regex_result.area_km2,
            locations            = locations or regex_result.locations,
            urgency_level        = regex_result.urgency_level,
            urgency_signals      = regex_result.urgency_signals,
            suggested_category   = regex_result.suggested_category,
            category_scores      = regex_result.category_scores,
            detected_language    = detected_lang,
            gcp_entities         = gcp_entities,
            extraction_method    = "gcp_nl",
        )

    # ------------------------------------------------------------------
    # Regex / keyword fallback
    # ------------------------------------------------------------------

    def _extract_regex(self, text: str) -> ExtractedEntities:
        lower = text.lower()

        # ── Population numbers ──────────────────────────────────────────
        pop_mentions = [
            int(m.replace(",", ""))
            for m in _POP_PATTERN.findall(text)
        ]
        affected_population = max(pop_mentions) if pop_mentions else None

        # ── Deaths ──────────────────────────────────────────────────────
        death_matches = [int(m.replace(",", "")) for m in _DEATH_PATTERN.findall(text)]
        death_count = max(death_matches) if death_matches else None

        # ── Area ────────────────────────────────────────────────────────
        area_matches = [float(m.replace(",", "")) for m in _AREA_PATTERN.findall(text)]
        area_km2 = max(area_matches) if area_matches else None

        # ── Disease cases ────────────────────────────────────────────────
        case_matches = [int(m.replace(",", "")) for m in _CASE_PATTERN.findall(text)]
        case_count = max(case_matches) if case_matches else None

        # ── Locations (naive: capitalised 2+ word sequences after "in/near/at") ──
        location_pattern = re.compile(
            r"(?:in|near|at|from|affecting)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})"
        )
        locations = list(dict.fromkeys(m.strip() for m in location_pattern.findall(text)))

        # ── Urgency ─────────────────────────────────────────────────────
        signals_found: List[str] = []
        for phrase in URGENCY_HIGH:
            if phrase in lower:
                signals_found.append(phrase)

        med_signals: List[str] = []
        for phrase in URGENCY_MED:
            if phrase in lower:
                med_signals.append(phrase)

        low_signals_present = any(phrase in lower for phrase in URGENCY_LOW)

        if signals_found:
            urgency_level = "high"
        elif med_signals:
            urgency_level = "medium"
            signals_found = med_signals
        elif low_signals_present:
            urgency_level = "low"
        else:
            urgency_level = "medium"  # unknown → conservative default

        # Bump urgency if deaths or cases are present
        if death_count and death_count > 0 and urgency_level != "high":
            urgency_level = "high"
            signals_found.append(f"{death_count} deaths mentioned")
        if case_count and case_count > 10 and urgency_level == "low":
            urgency_level = "medium"

        # ── Category hints ───────────────────────────────────────────────
        cat_scores: Dict[str, int] = {}
        for cat_key, keywords in _CATEGORY_HINTS.items():
            score = sum(1 for kw in keywords if kw in lower)
            if score:
                cat_scores[cat_key] = score

        suggested_category: Optional[str] = None
        if cat_scores:
            suggested_category = max(cat_scores, key=lambda k: cat_scores[k])

        return ExtractedEntities(
            affected_population  = affected_population,
            population_mentions  = pop_mentions,
            death_count          = death_count,
            case_count           = case_count,
            area_km2             = area_km2,
            locations            = locations[:10],   # cap for sanity
            urgency_level        = urgency_level,
            urgency_signals      = signals_found[:8],
            suggested_category   = suggested_category,
            category_scores      = cat_scores,
            detected_language    = "en",             # regex has no lang detection
            gcp_entities         = [],
            extraction_method    = "regex",
        )
