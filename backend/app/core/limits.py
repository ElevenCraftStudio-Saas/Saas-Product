"""Per-user event + storage quota helpers."""
import os

from sqlalchemy import func

from ..models import models

DEFAULT_EVENT_LIMIT = int(os.getenv("DEFAULT_EVENT_LIMIT", "2"))
DEFAULT_STORAGE_LIMIT_MB = int(os.getenv("DEFAULT_STORAGE_LIMIT_MB", "2048"))


def effective_event_limit(user) -> int:
    if getattr(user, "max_events", None) is not None:
        return user.max_events
    return DEFAULT_EVENT_LIMIT


def effective_storage_limit_mb(user) -> int:
    if getattr(user, "storage_limit_mb", None) is not None:
        return user.storage_limit_mb
    return DEFAULT_STORAGE_LIMIT_MB


def user_storage_used_bytes(db, user) -> int:
    """Sum of stored photo bytes across all events owned by the user."""
    total = (
        db.query(func.coalesce(func.sum(models.Photo.size_bytes), 0))
        .join(models.Event, models.Photo.event_id == models.Event.id)
        .filter(models.Event.photographer_id == user.id)
        .scalar()
    )
    return int(total or 0)
