import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
import os
import logging

from fastapi.staticfiles import StaticFiles

from .database import get_db, SessionLocal
from .core.limiter import limiter
from .routers import auth, events, photos, guest
from .services.s3_service import s3_service
from .services.folder_watcher import watcher_manager
from .services import retention

# Make application loggers (wedfind.*) visible — uvicorn only configures its own
# loggers, so without this our S3/upload/audit logs are silently dropped.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logging.getLogger("wedfind").setLevel(logging.INFO)

# NOTE: schema is now managed by Alembic migrations (`alembic upgrade head`),
# not Base.metadata.create_all().


async def _retention_loop():
    """Run the DPDP retention sweep on startup, then every 24h."""
    log = logging.getLogger("wedfind")
    while True:
        db = SessionLocal()
        try:
            result = await asyncio.to_thread(retention.purge_expired, db)
            if result["photos"]:
                log.info("retention sweep purged %s", result)
        except Exception:
            log.exception("retention sweep failed")
        finally:
            db.close()
        await asyncio.sleep(retention.SWEEP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Resume all enabled folder watches on startup (survives restart).
    try:
        watcher_manager.start_all()
    except Exception:
        logging.getLogger("wedfind").exception("Failed to start folder watchers")
    # Background DPDP retention sweeper.
    sweeper = asyncio.create_task(_retention_loop())
    yield
    # Clean shutdown.
    sweeper.cancel()
    watcher_manager.stop_all()


app = FastAPI(title="WedFind AI API", lifespan=lifespan)

# Rate limiting (per-IP) via SlowAPI.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Mount static files
app.mount("/uploads", StaticFiles(directory=os.getenv("UPLOAD_DIR", "../uploads")), name="uploads")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (legacy match.py removed — guest flow supersedes it)
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(photos.router, prefix="/api/photos", tags=["Photos"])
app.include_router(guest.router, prefix="/api/guest", tags=["Guest"])


@app.get("/")
def read_root():
    return {"message": "Welcome to WedFind AI API"}


@app.get("/healthz", tags=["Health"])
def healthz(db: Session = Depends(get_db)):
    """Liveness + dependency check: PostgreSQL and S3."""
    db_ok = False
    s3_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logging.getLogger("wedfind").exception("healthz: DB check failed")
    try:
        s3_service.s3_client.head_bucket(Bucket=s3_service.bucket_name)
        s3_ok = True
    except Exception:
        logging.getLogger("wedfind").exception("healthz: S3 check failed")

    status = "ok" if (db_ok and s3_ok) else "degraded"
    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "s3": "ok" if s3_ok else "error",
    }
