# NGO Volunteer Platform

A platform that connects NGOs managing community needs with skilled volunteers. Documents uploaded by NGOs are semantically analysed and scored for severity; the resulting events are shown on an interactive map and matched to volunteers based on skill, location, and reliability.

---

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+ (frontend)
- A Google Cloud project with billing enabled (free $300 credit from the Google Developer Program is sufficient)
- `gcloud` CLI authenticated: `gcloud auth application-default login`

### Backend

```bash
git clone https://github.com/Navyasri12355/volunteer-matchmaker.git
cd volunteer-matchmaker

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set GCP_PROJECT, FIREBASE_STORAGE_BUCKET at minimum

# Run the API server
uvicorn main:app --reload --port 8080
```

The API will be available at `http://localhost:8080`. Interactive docs at `http://localhost:8080/docs`.

### Offline / no-GCP mode

Set these in `.env` to disable all cloud API calls and use local fallbacks:

```
USE_VERTEX_EMBEDDINGS=false
USE_GCP_NL_API=false
USE_CLOUD_VISION=false
USE_CLOUD_TRANSLATE=false
```

The severity engine falls back to TF-IDF, entity extraction uses regex, and certificate uploads are queued for manual review.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Project structure

```
volunteer-matchmaker/
├── backend/
│   ├── config.py                   # Central settings
│   ├── ingestion/                  # Document parsing + chunking + ingest->severity bridge
│   │   ├── __init__.py
│   │   ├── ingestor.py
│   │   └── ingestor_to_severity.py
│   |
│   └── nlp/                        # NLP and scoring pipeline
│       ├── __init__.py
│       ├── category_config.py      # Category weights, subtypes, per-NGO config
│       ├── event_nlp_extractor.py  # Entity extraction (Cloud NL API / regex)
│       ├── severity_engine.py      # Composite severity score (Vertex AI)
│       ├── skill_verifier.py       # Certificate OCR (Cloud Vision API)
│       └── trust_scorer.py         # NGO trust score + volunteer points
│
├── config/
│   └── requirements.txt
├── docs/
│   ├── architecture.md         # System design and data flows
│   ├── scoring_logic.md        # Severity and trust scoring formulas
│   └── api_reference.md        # REST API endpoint reference
│
├── tests/                      # currently empty
├── pyproject.toml
└── README.md
```

---

## Event categories

| Category | Base severity weight |
|---|---|
| Disaster Relief | 1.00 |
| Water & Sanitation | 0.90 |
| Food Security | 0.85 |
| Education | 0.55 |
| Environment | 0.50 |
| Animal Welfare | 0.45 |

Each NGO defines its allowed categories at registration. One custom subtype per category is permitted.

---

## Severity scoring

Five-component composite score in [0, 1]:

```
score = nlp_score × category_weight × doc_strength × area_scale × recency_mult
```

| Component | Source |
|---|---|
| NLP semantic score | Vertex AI `text-embedding-005` vs severity anchors |
| Category weight | Domain-assigned urgency (see table above) |
| Document strength | Content volume + quantitative evidence + file count |
| Area scale | Log-scaled affected population or km² |
| Recency decay | Exponential half-life of 180 days; floor at 0.15 |

See [docs/scoring_logic.md](docs/scoring_logic.md) for the full formula with examples.

---

## Google Cloud services used

| Service | Purpose |
|---|---|
| Cloud Run | Backend hosting |
| Firestore | All structured data |
| Firebase Auth | Authentication (3 roles) |
| Firebase Storage | Uploaded documents and certificates |
| Vertex AI `text-embedding-005` | Semantic severity embeddings |
| Cloud Natural Language API | Entity extraction from event docs |
| Cloud Vision API | OCR on skill certificates |
| Cloud Translation API | Non-English document translation |

All services operate within the $300 Google Developer Program credit.

---

## Volunteer matching

- **CRITICAL events** — registered volunteers with verified matching skills are auto-assigned. Confirmation required within 24h; unconfirmed assignments are reassigned automatically.
- **MODERATE / LOW events** — open call; volunteers apply and NGO selects.

Matching rank factors: skill match · geographic proximity · preferred category · volunteer reliability score.

---

## Scoring and trust

- **NGO trust score** — internal only, admin-visible. Gates event creation (score ≥ 0.40 required). Updated via EMA after each post-event audit.
- **Volunteer points** — public, shown on profiles. Earned per event; multipliers for severity, skill use, early acceptance, and 5-star NGO review.
- Scores are never published publicly for NGOs. The Verified tag is admin-granted, not automatic.

---

## Docs

- [Architecture](docs/architecture.md)
- [Scoring logic](docs/scoring_logic.md)
- [API reference](docs/api_reference.md)

---

## Contributing

PRs welcome — please open an issue first to discuss significant changes.