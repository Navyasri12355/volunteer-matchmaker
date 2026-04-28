# NGO Volunteer Platform - Complete System Architecture

## Overview

This repository contains the full NGO Volunteer Platform system as described in the final architecture:

- **Firebase Auth** → User identity
- **Firebase Storage** → Document & certificate uploads
- **FastAPI** → REST API orchestration
- **PostgreSQL** → Persistent data layer
- **backend/** → NLP intelligence (unchanged)

## Project Structure

```
volunteer-matchmaker/
├── api/                    # FastAPI application
│   ├── main.py            # App entrypoint
│   ├── deps.py            # Dependency injection (auth, DB)
│   ├── core/              # Config, security, constants
│   ├── models/            # SQLAlchemy models (PostgreSQL)
│   ├── schemas/           # Pydantic request/response
│   ├── routes/            # API endpoints
│   ├── services/          # Business logic
│   └── db/                # Database session, migrations
│
├── backend/               # NLP & ingestion (UNCHANGED)
│   ├── ingestion/
│   └── nlp/
│
├── frontend/              # Next.js React app
│   ├── app/               # Pages (App Router)
│   ├── components/        # UI components
│   ├── lib/               # Firebase & API clients
│   └── public/
│
├── infra/                 # Infrastructure
│   ├── docker/            # Dockerfile & compose
│   └── gcp/               # GCP setup guides
│
├── scripts/               # Database & demo data setup
├── config/                # Dependencies (requirements.txt)
├── .env.example           # Environment template
└── README.md
```

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16
- GCP project with billing (for NLP services)

### 1. Backend Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file from template
cp .env.example .env
# Edit .env with your PostgreSQL and Firebase credentials

# Initialize database
python scripts/init_db.py

# Seed demo data (optional)
python scripts/seed_db.py

# Run API server
python api/main.py
# Or: uvicorn api.main:app --reload --port 8080
```

The API will be available at `http://localhost:8080`. Interactive docs at `http://localhost:8080/docs`.

### 2. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local from Firebase config
cp .env.example .env.local
# Edit .env.local with Firebase credentials

# Run development server
npm run dev
```

Frontend will be available at `http://localhost:3000`.

### 3. Docker Compose (All-in-One)

```bash
cd infra/docker

# Build and run
docker-compose up --build

# Initialize database inside container
docker exec volunteer-platform-api python scripts/init_db.py
docker exec volunteer-platform-api python scripts/seed_db.py
```

## Offline / No-GCP Mode

If you don't have GCP credentials, set in `.env`:

```
USE_VERTEX_EMBEDDINGS=false
USE_GCP_NL_API=false
USE_CLOUD_VISION=false
USE_CLOUD_TRANSLATE=false
```

The backend will fall back to:
- TF-IDF embeddings (local)
- Regex entity extraction
- Manual certificate review queue
- No translation

## Database Migrations (Alembic)

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Check migration status
alembic current
alembic history
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=api --cov=backend

# Run offline tests only (no GCP calls)
pytest -m offline
```

## Deployment

### Cloud Run (API)

```bash
# Build image
gcloud builds submit --tag gcr.io/<PROJECT_ID>/volunteer-platform-api

# Deploy to Cloud Run
gcloud run deploy volunteer-platform-api \
  --image gcr.io/<PROJECT_ID>/volunteer-platform-api \
  --platform managed \
  --region us-central1 \
  --set-env-vars DATABASE_URL=<CLOUD_SQL_CONN_STRING>
```

### Vercel (Frontend)

```bash
cd frontend

# Install Vercel CLI
npm install -g vercel

# Deploy
vercel
```

## Architecture Decisions

1. **PostgreSQL over Firestore** — PostgreSQL is the source of truth for structured data. Firestore handles identity only.
2. **FastAPI orchestration** — Single REST API entry point. Routes delegate to backend/ modules for intelligence.
3. **Firebase for auth & storage** — Firebase Auth handles user identity securely. Firebase Storage for documents and certificates.
4. **Next.js frontend** — Modern React framework with built-in SSR, optimized performance, and TypeScript support.
5. **Pydantic models** — Request/response validation + type safety across API boundary.
6. **SQLAlchemy ORM** — Type-safe DB layer, easy migrations, full Alembic support.

## Key APIs

### Authentication
- `POST /auth/register/ngo` — Register NGO manager
- `POST /auth/register/volunteer` — Register volunteer
- `POST /auth/login` — Get Firebase ID token

### Events
- `POST /events` — Create event (NGO, requires trust score ≥ 0.40)
- `GET /events` — List events (public, supports filtering)
- `GET /events/{event_id}` — Event details
- `PATCH /events/{event_id}` — Update event (NGO manager or admin)

### Volunteers
- `GET /volunteer/me` — Current volunteer profile
- `POST /volunteer/certificates` — Upload skill certificate
- `GET /volunteer/{volunteer_id}` — Public profile

### Assignments
- `POST /assignments/{event_id}/apply` — Apply to event
- `POST /assignments/{assignment_id}/confirm` — Confirm/decline assignment

### Audit & Scoring
- `POST /audit/{event_id}/ngo-feedback` — NGO submits post-event audit
- `POST /audit/{assignment_id}/volunteer-review` — Volunteer reviews NGO
- `POST /audit/{event_id}/award-points` — Admin awards points

See [docs/api_reference.md](docs/api_reference.md) for full endpoint documentation.

## Documentation

- [Architecture](docs/architecture.md) — System design and data flows
- [Scoring Logic](docs/scoring_logic.md) — Severity and trust scoring formulas
- [API Reference](docs/api_reference.md) — Endpoint details

## TODO / Future Work

- [ ] Firebase token verification (currently stubbed)
- [ ] Firebase Storage integration (certificates, documents)
- [ ] Volunteer matching engine (skill, location, reliability ranking)
- [ ] Admin dashboard (trust scores, audit logs)
- [ ] Email notifications (event matched, confirmation reminders)
- [ ] Map integration (Leaflet.js or Google Maps)
- [ ] Real-time chat for NGO ↔ volunteer communication
- [ ] Mobile app (React Native)

## Contributing

PRs welcome — please open an issue first to discuss significant changes.

## License

MIT