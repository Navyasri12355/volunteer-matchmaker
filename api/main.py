"""
FastAPI application entrypoint.

Orchestrates the backend NLP/ingestion, Firebase Auth, and PostgreSQL persistence.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from api.db.session import engine, Base
from api.db.bootstrap import ensure_user_password_column
from api.routes import auth, ngo, volunteer, events, assignments, audit


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup: create tables
    Base.metadata.create_all(bind=engine)
    ensure_user_password_column(engine)
    yield
    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="NGO Volunteer Platform API",
    description="Connects NGOs with volunteers using semantic severity scoring.",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [
    "http://localhost:3000",  # Default Next.js/React port
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # Default Vite port
]

# For local development it's useful to allow all origins to avoid CORS
# issues caused by preflight or error responses escaping middleware.
# In production, narrow this to explicit origins above and set
# `allow_credentials=True` if cookies/session auth is required.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.requests import Request
from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return a JSON error and include the Origin header so browsers receive CORS headers.

    This handler is intentionally simple for development so frontend receives
    a predictable JSON body and CORS headers on 500s. Replace or expand
    in production with safer error reporting.
    """
    origin = request.headers.get("origin")
    content = {"detail": "Internal server error"}
    headers = {}
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(status_code=500, content=content, headers=headers)

# Routes
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(ngo.router, prefix="/ngo", tags=["ngo"])
app.include_router(volunteer.router, prefix="/volunteer", tags=["volunteer"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(assignments.router, prefix="/assignments", tags=["assignments"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "volunteer-platform-api"}


@app.get("/")
async def root():
    """Basic landing response for browser requests."""
    return {"message": "NGO Volunteer Platform API is running"}


@app.get("/favicon.ico")
async def favicon():
    """Avoid 404s for browser favicon requests."""
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)
