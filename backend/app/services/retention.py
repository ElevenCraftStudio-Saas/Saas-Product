"""DPDP retention sweeper.

Events with `retention_days` set get their photos + face embeddings + S3
objects purged once `event_date + retention_days` has passed. Consent records
are kept (legal proof) — only the biometric/photo data is destroyed.

Idempotent: an already-purged event has no photos, so re-running is a no-op.
"""
import datetime
import logging
from typing import Optional

from sqlalchemy.orm import Session

from ..models import models
from . import activity
from .s3_service import s3_service

logger = logging.getLogger("wedfind.retention")

SWEEP_INTERVAL_SECONDS = 24 * 60 * 60  # daily


def scheduled_purge_at(event: models.Event) -> Optional[datetime.datetime]:
    """When this event's photos are due for deletion (None = keep forever)."""
    if event.retention_days is None or event.event_date is None:
        return None
    return event.event_date + datetime.timedelta(days=event.retention_days)


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _as_naive(dt: datetime.datetime) -> datetime.datetime:
    """event_date may be tz-naive (SQLite) — normalize for comparison."""
    if dt.tzinfo is not None:
        return dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


def purge_expired(db: Session) -> dict:
    """Delete photos/embeddings/S3 objects for all events past retention.

    Returns {"events": n, "photos": n} counts. Best-effort on S3.
    """
    now = _as_naive(_utcnow())
    events = (
        db.query(models.Event)
        .filter(models.Event.retention_days.isnot(None))
        .all()
    )

    events_purged = 0
    photos_purged = 0

    for event in events:
        due = scheduled_purge_at(event)
        if due is None or _as_naive(due) > now:
            continue

        photos = db.query(models.Photo).filter(models.Photo.event_id == event.id).all()
        if not photos:
            continue  # already purged / never had photos

        count = 0
        for photo in photos:
            if photo.storage_provider == "s3" and photo.storage_key:
                try:
                    s3_service.delete_file(photo.storage_key)
                except Exception:
                    logger.exception("retention: S3 delete failed key=%s", photo.storage_key)
            db.delete(photo)  # cascade removes face_embeddings + downloads
            count += 1

        db.commit()
        events_purged += 1
        photos_purged += count
        activity.log_activity(
            db, activity.RETENTION_PURGE, event_id=event.id,
            detail={"photos": count, "retention_days": event.retention_days},
        )
        logger.info("RETENTION_PURGE event=%s photos=%s", event.id, count)

    return {"events": events_purged, "photos": photos_purged}
