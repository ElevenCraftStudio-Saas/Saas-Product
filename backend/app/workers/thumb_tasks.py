"""Thumbnail Celery tasks (queue: thumbs)."""
import logging

from .celery_app import celery_app
from ..database import SessionLocal
from ..models import models
from ..services.thumbnails import make_thumbnail_for_photo

logger = logging.getLogger("wedfind.thumb")


@celery_app.task(
    name="app.workers.thumb_tasks.make_thumbnail",
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def make_thumbnail(photo_id: int):
    make_thumbnail_for_photo(photo_id)


@celery_app.task(name="app.workers.thumb_tasks.backfill_thumbnails")
def backfill_thumbnails(batch: int = 500):
    """Enqueue thumbnail generation for existing photos missing one (batched)."""
    db = SessionLocal()
    try:
        ids = [
            pid for (pid,) in db.query(models.Photo.id)
            .filter(models.Photo.thumb_key.is_(None))
            .limit(batch)
            .all()
        ]
    finally:
        db.close()
    for pid in ids:
        make_thumbnail.delay(pid)
    logger.info("backfill_thumbnails enqueued %s", len(ids))
    return {"enqueued": len(ids)}
