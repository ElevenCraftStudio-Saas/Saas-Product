"""Application configuration (fail-fast).

All settings come from the environment (or a local .env). Required variables
have no default — the process refuses to boot if any is missing. There is no
SQLite fallback in production; tests set DATABASE_URL explicitly.
"""
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
    SECRET_KEY: str
    ADMIN_EMAILS: str  # comma-separated; may be empty but must be set

    # --- Optional (sensible defaults) ---
    FRONTEND_URL: str = "http://localhost:3000"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    MATCH_THRESHOLD: float = 0.6
    DEFAULT_EVENT_LIMIT: int = 2
    DEFAULT_STORAGE_LIMIT_MB: int = 2048
    CONSENT_VERSION: str = "1.0"
    SENTRY_DSN: str | None = None
    ENV: str = "production"  # set ENV=development|test to relax HTTPS redirect
    # When false, ingest falls back to FastAPI BackgroundTasks/threads (rollback path).
    USE_CELERY: bool = True
    LOG_JSON: bool = True       # structured JSON logs; false = console (dev)
    ENABLE_METRICS: bool = True  # expose /metrics

    @property
    def admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"


# Instantiated at import → validation happens at startup. A missing required
# variable raises pydantic.ValidationError and the app/worker won't start.
settings = Settings()
