"""Scheduled maintenance Celery tasks (queue: maintenance, driven by beat)."""
import datetime
import logging

from .celery_app import celery_app
from ..database import SessionLocal
from ..models import models
from ..services import retention

logger = logging.getLogger("wedfind.maintenance")

# Photos stuck in PROCESSING longer than this are considered orphaned
# (worker killed mid-task) and re-enqueued.
STUCK_MINUTES = 15


@celery_app.task(name="app.workers.maintenance.retention_sweep")
def retention_sweep():
    """DPDP retention purge (was the in-web asyncio loop)."""
    db = SessionLocal()
    try:
        result = retention.purge_expired(db)
        if result.get("photos"):
            logger.info("retention sweep purged %s", result)
        return result
    finally:
        db.close()


@celery_app.task(name="app.workers.maintenance.reset_stuck_processing")
def reset_stuck_processing():
    """Reset photos wedged in PROCESSING (crashed worker) and re-enqueue them.

    Acts as the dead-letter recovery: at-least-once delivery + this sweep means
    a job is never silently lost."""
    from .face_tasks import process_photo

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=STUCK_MINUTES)
    db = SessionLocal()
    try:
        stuck = (
            db.query(models.Photo)
            .filter(
                models.Photo.processing_status == models.ProcessingStatus.PROCESSING,
                models.Photo.uploaded_at < cutoff,
            )
            .all()
        )
        ids = [p.id for p in stuck]
        for p in stuck:
            p.processing_status = models.ProcessingStatus.PENDING
        db.commit()
    finally:
        db.close()

    for pid in ids:
        process_photo.delay(pid)
    if ids:
        logger.warning("reset_stuck_processing re-enqueued %s photos", len(ids))
    return {"reset": len(ids)}
