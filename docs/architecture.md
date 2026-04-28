# Architecture

## Overview

The NGO Volunteer Platform is a Google Solution Challenge 2026 project that connects NGOs managing community needs with volunteers who can address them. Documents submitted by NGOs are ingested, semantically analysed, and scored for severity. The resulting events are shown on an interactive map and matched to volunteers based on skill, location, and reliability.

The backend is a Python FastAPI application deployed on Google Cloud Run. The frontend is a React single-page application. All persistent state lives in PostgreSQL. Uploaded files (PDFs, certificates) go to Firebase Storage (or local filesystem in offline mode).

---

## System diagram

```
NGO Manager / Volunteer
        │
        ▼
  React Frontend  ──────────────────────────────────┐
        │                                            │
        │ HTTPS                                      │ Firebase Auth (JWT)
        ▼                                            │
  FastAPI (Cloud Run)  ◄───────────────────────────┘
        │
        ├── backend/ingestion/  Parse PDFs, DOCX, MD, TXT (+ OCR)
        │        │
        │        ▼
        ├── backend/nlp/        Semantic scoring pipeline
        │   ├── severity_engine.py     Vertex AI embeddings
        │   ├── event_nlp_extractor.py Cloud NL API entities
        │   ├── category_config.py     Weights & subtypes
        │   ├── trust_scorer.py        NGO trust / vol points
        │   └── skill_verifier.py      Cloud Vision cert OCR
        │
        ▼
  PostgreSQL  ←──── all structured data
  Firebase Storage ←── uploaded docs & certificates (optional)
```

---

## Module responsibilities

### `backend/ingestion/`

Accepts uploads in PDF, DOCX, Markdown, and plain-text formats. Scanned PDFs without selectable text fall back to Tesseract OCR. Output is a flat list of `{content, metadata}` chunk dicts passed downstream to the NLP pipeline.

### `backend/nlp/`

The core intelligence layer. See [scoring_logic.md](scoring_logic.md) for the full scoring formula. Five modules:

| Module | Responsibility |
|---|---|
| `severity_engine.py` | Composite severity score in [0, 1] |
| `event_nlp_extractor.py` | Entity extraction: population, location, urgency |
| `category_config.py` | Category weights, subtypes, per-NGO allow-list |
| `trust_scorer.py` | NGO trust score (internal) + volunteer points (public) |
| `skill_verifier.py` | Certificate OCR and expiry validation |

### `backend/models/`

SQLAlchemy ORM models and helper classes:

| Module | Responsibility |
|---|---|
| `db_models.py` | Core ORM models (Volunteer, Event, Assignment, Audit, NGO) |
| `volunteer.py` | Helper methods for volunteer profile operations |
| `assignment.py` | State machine methods for assignment lifecycle |

### Planned API/domain modules

The architecture includes future service layers such as `events`, `audit`, and `auth`. In the current repository snapshot, the implemented Python packages are `backend/ingestion` and `backend/nlp`.

---

## Google Cloud services

| Service | Used for |
|---|---|
| **Cloud Run** | Host FastAPI backend |
| **PostgreSQL** | All structured data |
| **Firebase Auth** | User authentication |
| **Firebase Storage** | Uploaded docs & certs (optional) |
| **Vertex AI** `text-embedding-005` | Semantic severity embeddings |
| **Cloud Natural Language API** | Entity extraction from docs |
| **Cloud Vision API** | OCR on certificate images |
| **Cloud Translation API** | Non-English doc translation |
| **Google Maps / OpenStreetMap** | Event location map |

---

## Data flow: event creation

```
1. NGO manager uploads documents
2. backend/ingestion parses and chunks all files
3. event_nlp_extractor extracts: population, locations, urgency signals
4. severity_engine scores the event (NLP × category × area × recency × doc strength)
5. event_validator checks NGO trust score ≥ 0.40 threshold
6. Event is written to PostgreSQL with severity band + GeoJSON marker
7. Map layer updates; matching_engine queues volunteer assignment
```

## Data flow: post-event audit

```
1. NGO submits: attendance count, goal met (bool)
2. Volunteers submit: 1–5 star review of the NGO
3. audit_router aggregates both sides
4. trust_feedback_loop.py:
   - Updates NGOTrustScore via EMA (α=0.25) in PostgreSQL
   - Awards volunteer points via VolunteerPointsLedger in PostgreSQL
5. Admin sees updated internal NGO score; volunteer points are public
```

---

## Offline / degraded mode

Every Google Cloud API call has a fallback:

- Vertex AI embeddings → TF-IDF cosine similarity (scikit-learn)
- Cloud NL entity extraction → regex patterns for numbers and locations
- Cloud Vision OCR → certificate queued for manual admin review
- Cloud Translation → original text passed untranslated (with a warning)

The `USE_VERTEX_EMBEDDINGS`, `USE_GCP_NL_API`, `USE_CLOUD_VISION`, and `USE_CLOUD_TRANSLATE` env vars (see `.env.example`) toggle each service independently, so the system remains functional in local dev without any GCP credentials.

---

## Security notes

- NGO trust scores and composite scores are **never exposed via any public API endpoint**. Only the `admin` role can query them.
- Volunteer reliability scores are used internally for matching but are not shown on public profiles; only total points are public.
- Firebase Storage rules restrict certificate access to the owning volunteer and admins.
- The event creation endpoint validates `CategoryConfig.is_category_allowed()` server-side so NGOs cannot submit events in categories they did not register for.
