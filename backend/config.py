"""
config.py
---------
Central configuration object for the ngo-platform backend.

All modules import from here rather than reading os.getenv() themselves.
This makes it easy to swap values in tests without patching os.environ.

Usage
~~~~~
    from backend.config import settings

    if settings.use_vertex_embeddings:
        engine = SeverityEngine(use_vertex=True, gcp_project=settings.gcp_project)
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Reads from environment variables and .env file.
    All fields have safe defaults for local / offline dev.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Google Cloud ──────────────────────────────────────────────────
    gcp_project:  str = ""
    gcp_location: str = "us-central1"
    google_application_credentials: str = ""
    firebase_storage_bucket: str = ""

    # ── NLP feature flags ─────────────────────────────────────────────
    use_vertex_embeddings:  bool = True
    use_gcp_nl_api:         bool = True
    use_cloud_vision:       bool = True
    use_cloud_translate:    bool = True

    # ── Severity scoring ──────────────────────────────────────────────
    severity_band_critical: float = 0.70
    severity_band_moderate: float = 0.40

    # ── Trust scoring ─────────────────────────────────────────────────
    ngo_trust_gate_threshold: float = 0.40
    ngo_trust_ema_alpha:      float = 0.25

    # ── API ───────────────────────────────────────────────────────────
    api_host: str  = "0.0.0.0"
    api_port: int  = 8080
    debug:    bool = False

    # ── Convenience flags ─────────────────────────────────────────────
    @property
    def gcp_available(self) -> bool:
        """True if a GCP project is configured (embeddings / NL / Vision will work)."""
        return bool(self.gcp_project)

    @property
    def offline_mode(self) -> bool:
        """True when no GCP credentials are present (CI, local dev without creds)."""
        return not self.gcp_available


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton settings object (cached after first call)."""
    return Settings()


# Module-level alias so callers can just do `from config import settings`
settings = get_settings()