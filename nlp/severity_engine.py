"""
Severity Scoring Engine
-----------------------
Computes a composite severity score for community-need events submitted by NGOs.

Score components
~~~~~~~~~~~~~~~~
1. **Semantic NLP score**   – cosine similarity between the document embedding
   and a bank of severity anchor phrases, via Google Vertex AI
   ``text-embedding-005`` (formerly textembedding-gecko).  Falls back to a
   keyword-TF-IDF approach when Vertex is unavailable (e.g. dev / offline).

2. **Category weight**      – each of the six event categories carries a base
   urgency weight derived from domain knowledge.

3. **Area scale factor**    – larger affected populations / geographic areas
   amplify the raw score.

4. **Recency decay**        – documents older than ~6 months are down-weighted
   exponentially; anything > 1 year old is capped at a very low multiplier.

5. **Document strength**    – a lightweight proxy for how much supporting
   evidence was provided (character count, number of docs, presence of
   quantitative claims).

The final score is in [0, 1] and maps to three bands:
    CRITICAL  ≥ 0.70   → red    on the map
    MODERATE  ≥ 0.40   → orange
    LOW        < 0.40  → yellow

Usage
~~~~~
    from severity_engine import SeverityEngine, EventInput

    engine = SeverityEngine()          # authenticates via ADC or env vars
    result = engine.score(event)
    print(result.score, result.band, result.breakdown)

Google Cloud services used
~~~~~~~~~~~~~~~~~~~~~~~~~~
- **Vertex AI Text Embeddings** (``text-embedding-005``)  – within the free
  tier / $300 credit available through Google Developer Program.
- **Cloud Translation API** (v3 basic) – optional, for non-English docs;
  also within the free 500k chars/month quota.

Authentication
~~~~~~~~~~~~~~
Set ``GOOGLE_APPLICATION_CREDENTIALS`` to a service-account JSON file, **or**
run ``gcloud auth application-default login`` in dev.  Set ``GCP_PROJECT`` and
``GCP_LOCATION`` env vars (defaults: project from ADC, location "us-central1").
"""

from __future__ import annotations

import logging
import math
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / configuration
# ---------------------------------------------------------------------------

# Maps each event category to a base urgency weight in [0, 1].
# Disaster relief is inherently time-critical; animal welfare less so on
# average (but a severe case will still score high via the NLP component).
CATEGORY_WEIGHTS: Dict[str, float] = {
    "disaster_relief":      1.00,
    "water_and_sanitation": 0.90,
    "food":                 0.85,
    "education":            0.55,
    "environment":          0.50,
    "animal_welfare":       0.45,
    # custom subtypes fall back to 0.60
    "_custom":              0.60,
}

# Severity anchor phrases used to build the "ideal severe document" embedding.
# Grouped by theme so the centroid is balanced.
SEVERITY_ANCHORS: List[str] = [
    # Immediacy / life threat
    "urgent immediate life-threatening emergency crisis",
    "people are dying deaths occurring critical situation",
    "mass casualties severe injuries medical emergency",
    "acute shortage critical lack of essential resources",
    # Scale / scope
    "large population affected thousands displaced",
    "widespread devastation entire community impacted",
    "multiple villages regions affected large scale disaster",
    # Specific high-severity needs
    "no access to clean drinking water cholera outbreak",
    "severe acute malnutrition children starving food crisis",
    "shelter destroyed families homeless extreme weather",
    "disease outbreak epidemic uncontrolled spread infection",
    "flooding submerged homes evacuation required",
    # Temporal urgency
    "immediate action required within 24 hours",
    "situation deteriorating rapidly no time to delay",
    "critical window closing resources running out",
]

# Low-severity anchors (used to calibrate the opposite end of the scale)
LOW_SEVERITY_ANCHORS: List[str] = [
    "routine maintenance scheduled activity annual event",
    "awareness campaign educational workshop community meeting",
    "long term development gradual improvement program",
    "minor issue low priority improvement suggested",
    "ongoing stable situation monitoring required",
]

# Recency decay: half-life in days (score halves every HALF_LIFE_DAYS beyond
# the DECAY_START_DAYS grace period).
DECAY_START_DAYS = 90       # no penalty for docs < 3 months old
HALF_LIFE_DAYS   = 180      # score halves every 6 months after that
MIN_RECENCY_MULTIPLIER = 0.15  # floor – very old docs still count a little

# Bands
BAND_CRITICAL = 0.70
BAND_MODERATE = 0.40


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class SeverityBand(str, Enum):
    CRITICAL = "CRITICAL"   # red
    MODERATE = "MODERATE"   # orange
    LOW      = "LOW"        # yellow


@dataclass
class EventInput:
    """All information the scoring engine needs about a single event submission."""

    # Core identity
    category: str                        # one of the six categories or a custom string
    subtype: Optional[str] = None

    # Text content (from ingestor chunks – pass the combined text or raw chunks)
    document_texts: List[str] = field(default_factory=list)

    # Structured metadata
    affected_population: Optional[int]  = None   # estimated number of people
    affected_area_km2:   Optional[float] = None  # square kilometres
    location_name:       str            = ""

    # When was the need first reported / when are the docs from?
    reported_at: Optional[datetime] = None       # tz-aware preferred

    # Language of docs (ISO 639-1, e.g. "en", "fr", "hi").  None → auto-detect.
    language: Optional[str] = None

    # Number of supporting documents attached
    num_supporting_docs: int = 1

    # Free-form extra context (NGO manager's own description)
    manager_context: str = ""


@dataclass
class SeverityResult:
    score: float                   # final composite in [0, 1]
    band:  SeverityBand
    map_color: str                 # hex colour for map rendering
    breakdown: Dict[str, float]    # component scores for explainability
    top_evidence: List[str]        # sentences that drove the score (for audit)
    warnings: List[str]            # e.g. "document too old", "no text found"


# ---------------------------------------------------------------------------
# Embedding back-ends
# ---------------------------------------------------------------------------

class _VertexEmbedder:
    """Thin wrapper around Vertex AI text-embedding-005."""

    MODEL = "text-embedding-005"

    def __init__(self, project: str, location: str):
        from google.cloud import aiplatform                          # type: ignore
        from vertexai.language_models import TextEmbeddingModel     # type: ignore
        aiplatform.init(project=project, location=location)
        self._model = TextEmbeddingModel.from_pretrained(self.MODEL)
        logger.info("Vertex AI embedder initialised (model=%s)", self.MODEL)

    def embed(self, texts: List[str]) -> np.ndarray:
        """Return (N, D) float32 array."""
        # Batch in groups of 5 to stay within API limits
        all_vectors = []
        batch_size = 5
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = self._model.get_embeddings(batch)
            all_vectors.extend([e.values for e in embeddings])
        return np.array(all_vectors, dtype=np.float32)


class _TFIDFEmbedder:
    """
    Offline fallback: TF-IDF vectors.  Lower quality but zero cloud cost.
    Automatically used when Vertex AI credentials are absent.
    """

    def __init__(self, corpus: List[str]):
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        self._vec = TfidfVectorizer(ngram_range=(1, 2), max_features=4096)
        self._vec.fit(corpus)
        logger.info("TF-IDF fallback embedder initialised (offline mode)")

    def embed(self, texts: List[str]) -> np.ndarray:
        return self._vec.transform(texts).toarray().astype(np.float32)


# ---------------------------------------------------------------------------
# Translation helper (optional)
# ---------------------------------------------------------------------------

def _translate_to_english(texts: List[str], project: str) -> List[str]:
    """Translate a list of texts to English using Cloud Translation API (v3 basic).

    Returns the original texts unchanged on any error.
    """
    try:
        from google.cloud import translate_v2 as translate  # type: ignore
        client = translate.Client()
        translated = []
        for t in texts:
            if not t.strip():
                translated.append(t)
                continue
            result = client.translate(t, target_language="en")
            translated.append(result["translatedText"])
        return translated
    except Exception as exc:
        logger.warning("Translation failed, using original text. Error: %s", exc)
        return texts


# ---------------------------------------------------------------------------
# Core scoring helpers
# ---------------------------------------------------------------------------

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _recency_score(reported_at: Optional[datetime]) -> Tuple[float, Optional[str]]:
    """
    Returns a multiplier in [MIN_RECENCY_MULTIPLIER, 1.0] and an optional
    warning string if the document is stale.
    """
    if reported_at is None:
        # Unknown date – apply a small default penalty
        return 0.75, "Document date unknown; moderate recency penalty applied."

    now = datetime.now(timezone.utc)
    if reported_at.tzinfo is None:
        reported_at = reported_at.replace(tzinfo=timezone.utc)

    age_days = (now - reported_at).days
    if age_days < 0:
        age_days = 0  # future-dated doc (shouldn't happen, treat as fresh)

    if age_days <= DECAY_START_DAYS:
        return 1.0, None

    excess_days = age_days - DECAY_START_DAYS
    multiplier = 0.5 ** (excess_days / HALF_LIFE_DAYS)
    multiplier = max(multiplier, MIN_RECENCY_MULTIPLIER)

    warning = None
    if age_days > 365:
        warning = f"Documents are {age_days} days old (> 1 year); heavily down-weighted."
    elif age_days > 180:
        warning = f"Documents are {age_days} days old (> 6 months); recency penalty applied."

    return multiplier, warning


def _area_scale_factor(population: Optional[int], area_km2: Optional[float]) -> float:
    """
    Sigmoid-like scale in [0.5, 1.5].
    Large = more people / larger area → amplifies score.
    Small / unknown → neutral multiplier of 1.0.
    """
    # Use whichever proxy we have; prefer population
    if population is not None and population > 0:
        # log10(1000) → ~1.0, log10(100000) → ~1.4
        raw = math.log10(max(population, 1)) / 5.0   # normalise to ~[0,1]
    elif area_km2 is not None and area_km2 > 0:
        raw = math.log10(max(area_km2, 0.1)) / 4.0
    else:
        return 1.0  # neutral

    # Map raw → [0.5, 1.5]
    scale = 0.5 + raw
    return max(0.5, min(1.5, scale))


def _document_strength(texts: List[str], num_docs: int) -> float:
    """
    Simple heuristic for how much supporting evidence exists.
    Returns a value in [0.5, 1.0].

    Signals:
    - Total character count (more content = more evidence)
    - Presence of numbers / statistics (e.g. "450 families", "3 km²")
    - Multiple documents
    """
    combined = " ".join(texts)
    char_count = len(combined)

    # How many numeric claims appear? (crude proxy for quantitative evidence)
    numeric_matches = len(re.findall(r"\b\d[\d,]*\.?\d*\s*(%|km|people|families|children|cases|villages|deaths|injured|displaced)", combined, re.IGNORECASE))

    # Normalise
    content_score  = min(char_count / 5000, 1.0)           # saturates at 5 000 chars
    numeric_score  = min(numeric_matches / 5, 1.0)          # saturates at 5 hits
    doc_count_score = min(num_docs / 3, 1.0)                # saturates at 3 docs

    strength = 0.50 + 0.20 * content_score + 0.20 * numeric_score + 0.10 * doc_count_score
    return round(min(strength, 1.0), 4)


def _extract_top_sentences(texts: List[str], embedder, anchor_vec: np.ndarray, top_n: int = 3) -> List[str]:
    """
    Return the top_n sentences most similar to the severity anchor centroid.
    Used for the 'evidence' field in the result (explainability / audit).
    """
    sentences = []
    for text in texts:
        # Simple sentence split
        for sent in re.split(r"(?<=[.!?])\s+", text):
            s = sent.strip()
            if len(s) > 20:
                sentences.append(s)

    if not sentences:
        return []

    try:
        sent_vecs = embedder.embed(sentences)
        sims = [_cosine_similarity(v, anchor_vec) for v in sent_vecs]
        ranked = sorted(zip(sims, sentences), reverse=True)
        return [s for _, s in ranked[:top_n]]
    except Exception:
        return sentences[:top_n]


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class SeverityEngine:
    """
    Instantiate once (expensive: loads/trains embedder and pre-computes anchors).
    Then call `.score(event)` for each event.

    Parameters
    ----------
    use_vertex : bool
        If True, attempt to use Vertex AI embeddings (requires GCP credentials).
        If False, or if credentials are absent, falls back to TF-IDF.
    gcp_project : str | None
        GCP project ID.  Reads from ``GCP_PROJECT`` env var if None.
    gcp_location : str
        Vertex AI region.  Defaults to ``us-central1``.
    translate_non_english : bool
        If True, translate non-English docs to English before embedding.
        Uses Cloud Translation API (free 500k chars/month).
    """

    def __init__(
        self,
        use_vertex: bool = True,
        gcp_project: Optional[str] = None,
        gcp_location: str = "us-central1",
        translate_non_english: bool = True,
    ):
        self._project   = gcp_project or os.getenv("GCP_PROJECT", "")
        self._location  = gcp_location
        self._translate = translate_non_english
        self._embedder  = self._init_embedder(use_vertex)

        # Pre-compute anchor embeddings
        logger.info("Pre-computing severity anchor embeddings…")
        all_anchors = SEVERITY_ANCHORS + LOW_SEVERITY_ANCHORS
        anchor_vecs = self._embedder.embed(all_anchors)

        n_high = len(SEVERITY_ANCHORS)
        self._high_anchor = anchor_vecs[:n_high].mean(axis=0)   # centroid of high-severity
        self._low_anchor  = anchor_vecs[n_high:].mean(axis=0)   # centroid of low-severity
        logger.info("Anchor embeddings ready.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, event: EventInput) -> SeverityResult:
        """Compute and return a SeverityResult for the given EventInput."""
        warnings: List[str] = []
        t0 = time.perf_counter()

        # 1. Gather + optionally translate text
        texts = [t for t in event.document_texts if t.strip()]
        if event.manager_context.strip():
            texts.append(event.manager_context)

        if not texts:
            warnings.append("No document text provided; scoring entirely from metadata.")
            nlp_score = 0.3   # conservative default
            top_evidence: List[str] = []
        else:
            if self._translate and event.language and event.language.lower() != "en":
                texts = _translate_to_english(texts, self._project)

            nlp_score, top_evidence = self._nlp_score(texts)

        # 2. Category weight
        cat_key = event.category.lower().replace(" ", "_")
        cat_weight = CATEGORY_WEIGHTS.get(cat_key, CATEGORY_WEIGHTS["_custom"])

        # 3. Area scale
        area_factor = _area_scale_factor(event.affected_population, event.affected_area_km2)

        # 4. Recency
        recency_mult, rec_warn = _recency_score(event.reported_at)
        if rec_warn:
            warnings.append(rec_warn)

        # 5. Document strength
        doc_strength = _document_strength(texts, event.num_supporting_docs)

        # 6. Composite
        # Formula (all components explained in module docstring):
        #   base     = nlp_score * cat_weight
        #   adjusted = base * doc_strength * area_factor * recency_mult
        # Clamp to [0, 1]
        base     = nlp_score * cat_weight
        adjusted = base * doc_strength * area_factor * recency_mult
        final    = round(max(0.0, min(1.0, adjusted)), 4)

        band, color = self._band_and_color(final)

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        logger.info(
            "Scored event [%s / %s] → %.3f (%s) in %s ms",
            event.category, event.location_name or "?", final, band.value, elapsed_ms,
        )

        return SeverityResult(
            score=final,
            band=band,
            map_color=color,
            breakdown={
                "nlp_semantic":      round(nlp_score, 4),
                "category_weight":   round(cat_weight, 4),
                "area_scale":        round(area_factor, 4),
                "recency_mult":      round(recency_mult, 4),
                "doc_strength":      round(doc_strength, 4),
                "base_score":        round(base, 4),
                "final_score":       final,
            },
            top_evidence=top_evidence,
            warnings=warnings,
        )

    def score_batch(self, events: List[EventInput]) -> List[SeverityResult]:
        """Score multiple events. Results are in the same order as inputs."""
        return [self.score(e) for e in events]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_embedder(self, use_vertex: bool):
        if use_vertex and self._project:
            try:
                return _VertexEmbedder(self._project, self._location)
            except Exception as exc:
                logger.warning(
                    "Could not initialise Vertex AI embedder (%s). "
                    "Falling back to TF-IDF.",
                    exc,
                )
        logger.info("Using offline TF-IDF embedder (no GCP credentials / project).")
        return _TFIDFEmbedder(corpus=SEVERITY_ANCHORS + LOW_SEVERITY_ANCHORS)

    def _nlp_score(self, texts: List[str]) -> Tuple[float, List[str]]:
        """
        Embed the document text, compute:
          similarity to HIGH anchors  →  high_sim
          similarity to LOW anchors   →  low_sim

        NLP score = (high_sim - low_sim + 1) / 2   (maps [-1,1] → [0,1])

        Also returns the top evidence sentences.
        """
        combined = " ".join(texts)

        # Chunk into ≤ 2 000-char pieces for embedding
        chunk_size = 2000
        chunks = [combined[i : i + chunk_size] for i in range(0, len(combined), chunk_size)]
        if not chunks:
            return 0.3, []

        try:
            chunk_vecs = self._embedder.embed(chunks)
        except Exception as exc:
            logger.warning("Embedding failed: %s – returning default NLP score.", exc)
            return 0.3, []

        # Aggregate chunk vectors (mean pooling)
        doc_vec = chunk_vecs.mean(axis=0)

        high_sim = _cosine_similarity(doc_vec, self._high_anchor)
        low_sim  = _cosine_similarity(doc_vec, self._low_anchor)

        # Calibrated to [0, 1]
        raw_score = (high_sim - low_sim + 1.0) / 2.0
        nlp_score = max(0.0, min(1.0, raw_score))

        top_evidence = _extract_top_sentences(texts, self._embedder, self._high_anchor)

        return nlp_score, top_evidence

    @staticmethod
    def _band_and_color(score: float) -> Tuple[SeverityBand, str]:
        if score >= BAND_CRITICAL:
            return SeverityBand.CRITICAL, "#E53E3E"   # red
        elif score >= BAND_MODERATE:
            return SeverityBand.MODERATE, "#DD6B20"   # orange
        else:
            return SeverityBand.LOW, "#D69E2E"        # yellow


# ---------------------------------------------------------------------------
# Map rendering helper  (OpenStreetMap / Leaflet compatible)
# ---------------------------------------------------------------------------

def build_map_marker(event_input: EventInput, result: SeverityResult) -> dict:
    """
    Returns a GeoJSON-style Feature dict that can be consumed directly by a
    Leaflet.js front-end or stored in Firestore for the map layer.

    Circle radius is proportional to affected_area_km2 / affected_population.
    """
    radius_m = 5000  # default 5 km
    if event_input.affected_area_km2:
        radius_m = int(math.sqrt(event_input.affected_area_km2 / math.pi) * 1000)
    elif event_input.affected_population:
        # Rough heuristic: 100 000 people → 10 km radius
        radius_m = int(math.sqrt(event_input.affected_population / math.pi) * 10)
    radius_m = max(500, min(radius_m, 100_000))

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            # Caller is responsible for geocoding location_name → lat/lng
            "coordinates": [None, None],
        },
        "properties": {
            "location":       event_input.location_name,
            "category":       event_input.category,
            "severity_score": result.score,
            "severity_band":  result.band.value,
            "color":          result.map_color,
            "radius_m":       radius_m,
            "top_evidence":   result.top_evidence,
            "breakdown":      result.breakdown,
            "warnings":       result.warnings,
        },
    }


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    engine = SeverityEngine(use_vertex=False)   # offline TF-IDF for smoke test

    sample_events = [
        EventInput(
            category="disaster_relief",
            document_texts=[
                "Flooding has submerged 3 villages. Over 2 000 families have lost their homes. "
                "Urgent rescue operations required immediately. People are stranded on rooftops "
                "without food or water. At least 12 deaths reported. Medical emergency declared."
            ],
            affected_population=10000,
            affected_area_km2=45.0,
            reported_at=datetime.now(timezone.utc),
            location_name="Assam, India",
            num_supporting_docs=3,
        ),
        EventInput(
            category="education",
            document_texts=[
                "We are planning an annual school supplies drive for the local community. "
                "The program runs every October and benefits around 200 children. "
                "Volunteers are needed to sort and pack materials."
            ],
            affected_population=200,
            reported_at=datetime.now(timezone.utc),
            location_name="Bengaluru, India",
            num_supporting_docs=1,
        ),
        EventInput(
            category="water_and_sanitation",
            document_texts=[
                "The village has had no access to clean drinking water for 3 weeks. "
                "Cholera cases are rising—45 confirmed, 3 deaths. Immediate intervention "
                "is critical. The only water source is contaminated. 800 people at risk."
            ],
            affected_population=800,
            reported_at=datetime(2024, 1, 1, tzinfo=timezone.utc),  # old doc
            location_name="Rural Maharashtra, India",
            num_supporting_docs=2,
        ),
    ]

    print("\n" + "=" * 60)
    for i, event in enumerate(sample_events, 1):
        result = engine.score(event)
        print(f"\n[Event {i}] {event.category} — {event.location_name}")
        print(f"  Score : {result.score:.3f}  |  Band : {result.band.value}  |  Color: {result.map_color}")
        print(f"  Breakdown:")
        for k, v in result.breakdown.items():
            print(f"    {k:<20} {v}")
        if result.top_evidence:
            print(f"  Top evidence:")
            for e in result.top_evidence:
                print(f"    • {e[:120]}")
        if result.warnings:
            print(f"  ⚠ Warnings: {result.warnings}")
    print("\n" + "=" * 60)
