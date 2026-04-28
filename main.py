"""
Main FastAPI application entry point.

Mounts routers for:
- Map API (events for map view)
- Volunteer API (registration, matching, assignments)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import map_routes, volunteer_routes
from backend.config import settings

# Create main app
app = FastAPI(
    title="Volunteer Matchmaker",
    description="NGO Volunteer Platform — Matching & Assignments",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(map_routes.router)
app.include_router(volunteer_routes.router)


@app.get("/health", tags=["health"])
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "gcp_available": settings.gcp_available,
        "offline_mode": settings.offline_mode,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
