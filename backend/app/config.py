"""Application configuration (fail-fast).

All settings come from the environment (or a local .env). Required variables
have no default — the process refuses to boot if any is missing. There is no
SQLite fallback in production; tests set DATABASE_URL explicitly.

Roles are managed via Firestore (see services/firestore_service.py) — the
ADMIN_EMAILS env-var approach has been removed.
"""
import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- Required (boot fails if missing) ---
    DATABASE_URL: str
    REDIS_URL: str
    AWS_REGION: str
    # Accept the legacy AWS_BUCKET_NAME name too so existing .env files keep working.
    S3_BUCKET: str = Field(validation_alias=AliasChoices("S3_BUCKET", "AWS_BUCKET_NAME"))
    FIREBASE_PROJECT_ID: str

    # --- Optional (sensible defaults) ---
    UPLOAD_DIR: str = "uploads"
    FRONTEND_URL: str = "http://localhost:3000"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    MATCH_THRESHOLD: float = 0.6
    DEFAULT_EVENT_LIMIT: int = 2
    DEFAULT_STORAGE_LIMIT_MB: int = 51200  # 50 GB per studio
    CONSENT_VERSION: str = "1.0"
    # Signs guest download tokens (core/signing.py). Unset → ephemeral
    # per-process key (dev only; tokens die on restart).
    SECRET_KEY: str | None = None
    SENTRY_DSN: str | None = None
    # Base64-encoded Firebase service-account JSON (alternative to GOOGLE_APPLICATION_CREDENTIALS).
    # Decoded and written to FIREBASE_CREDENTIALS at startup by firebase.py.
    FIREBASE_SERVICE_ACCOUNT_B64: str | None = None
    ENV: str = "production"  # set ENV=development|test to relax HTTPS redirect
    # When false, ingest falls back to FastAPI BackgroundTasks/threads (rollback path).
    USE_CELERY: bool = True
    LOG_JSON: bool = True       # structured JSON logs; false = console (dev)
    ENABLE_METRICS: bool = True  # expose /metrics

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    def upload_url_for(self, filepath: str) -> str:
        """Convert a stored filesystem path to a /uploads URL path.

        Handles both legacy '../uploads/...' paths and new absolute paths
        rooted at UPLOAD_DIR.
        """
        upload_dir = self.UPLOAD_DIR.replace("\\", "/").rstrip("/")
        normalised = filepath.replace("\\", "/")
        if normalised.startswith(upload_dir):
            rel = normalised[len(upload_dir):].lstrip("/")
        elif normalised.startswith("../uploads"):
            rel = normalised.replace("../uploads", "", 1).lstrip("/")
        else:
            rel = normalised
        return f"/uploads/{rel}"


# Instantiated at import → validation happens at startup. A missing required
# variable raises pydantic.ValidationError and the app/worker won't start.
settings = Settings()
