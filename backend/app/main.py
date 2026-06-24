import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
import os
import logging

from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import get_db, SessionLocal
from .core.limiter import limiter
from .core.security import SecurityHeadersMiddleware
from .routers import auth, events, photos, guest, admin
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
    # Background DPDP retention sweeper. With Celery enabled this runs as a
    # beat task instead (single replica) — don't duplicate it in every web worker.
    sweeper = None
    if not settings.USE_CELERY:
        sweeper = asyncio.create_task(_retention_loop())
    yield
    # Clean shutdown.
    if sweeper is not None:
        sweeper.cancel()
    watcher_manager.stop_all()


app = FastAPI(title="WedFind AI API", lifespan=lifespan)

# Security headers on every response; force HTTPS in production only.
app.add_middleware(SecurityHeadersMiddleware)
if settings.is_production:
    app.add_middleware(HTTPSRedirectMiddleware)

# Rate limiting (per-IP) via SlowAPI.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Mount static files
app.mount("/uploads", StaticFiles(directory=os.getenv("UPLOAD_DIR", "../uploads")), name="uploads")

# Configure CORS. FRONTEND_URL may be a comma-separated list. Localhost dev
# origins are only added OUTSIDE production (avoid trusting them in prod).
_allowed_origins = {o.strip() for o in settings.FRONTEND_URL.split(",") if o.strip()}
if not settings.is_production:
    _allowed_origins |= {
        "http://localhost:3000", "http://localhost:3001",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001",
    }
_allowed_origins = sorted(_allowed_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (legacy match.py removed — guest flow supersedes it)
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(photos.router, prefix="/api/photos", tags=["Photos"])
app.include_router(guest.router, prefix="/api/guest", tags=["Guest"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.get("/")
def read_root():
    return {"message": "Welcome to WedFind AI API"}


@app.get("/livez", tags=["Health"])
def livez():
    """Liveness: the process is up. No dependency checks (probe must not flap)."""
    return {"status": "ok"}


def _check_db(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        logging.getLogger("wedfind").exception("readyz: DB check failed")
        return False


def _check_redis() -> bool:
    try:
        import redis  # imported lazily so the web tier needn't hard-depend at import
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        return bool(client.ping())
    except Exception:
        logging.getLogger("wedfind").exception("readyz: Redis check failed")
        return False


def _check_s3() -> bool:
    try:
        s3_service.s3_client.head_bucket(Bucket=s3_service.bucket_name)
        return True
    except Exception:
        logging.getLogger("wedfind").exception("readyz: S3 check failed")
        return False


@app.get("/readyz", tags=["Health"])
def readyz(db: Session = Depends(get_db)):
    """Readiness: verify PostgreSQL, Redis and S3. Returns 503 when degraded."""
    checks = {"db": _check_db(db), "redis": _check_redis(), "s3": _check_s3()}
    ok = all(checks.values())
    body = {"status": "ok" if ok else "degraded", **{k: ("ok" if v else "error") for k, v in checks.items()}}
    return JSONResponse(body, status_code=200 if ok else 503)


# Back-compat alias (kept so existing probes/scripts don't break).
@app.get("/healthz", tags=["Health"])
def healthz(db: Session = Depends(get_db)):
    return readyz(db)
