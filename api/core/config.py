"""
Environment and application configuration.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Load from .env file."""

    # Database
    database_url: str = "postgresql://postgres:postgres@136.113.109.50:5432/ngo-volunteer-docu-db"

    # Firebase
    firebase_project_id: str = ""
    firebase_api_key: str = ""
    firebase_auth_domain: str = ""
    firebase_storage_bucket: str = ""

    # Google Cloud
    gcp_project: str = "volunteer-matcher-googlesol"
    gcp_location: str = "us-central1"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    debug: bool = False

    # Local upload storage
    local_upload_root: str = "./uploads"
    max_upload_mb: int = 20

    # NLP feature flags
    use_vertex_embeddings: bool = True
    use_gcp_nl_api: bool = True
    use_cloud_vision: bool = True
    use_cloud_translate: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
