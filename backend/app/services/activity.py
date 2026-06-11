"""Activity / audit logging.

Writes a row to activity_logs AND emits a structured log line. Best-effort:
a logging failure must never break the guest flow.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session
from ..models import models

logger = logging.getLogger("wedfind.activity")

# Allowed actions (kept as constants to avoid typos at call sites).
EVENT_VIEWED = "EVENT_VIEWED"
SELFIE_UPLOADED = "SELFIE_UPLOADED"
FACE_MATCH_COMPLETED = "FACE_MATCH_COMPLETED"
PHOTO_DOWNLOADED = "PHOTO_DOWNLOADED"


def log_activity(
    db: Session,
    action: str,
    *,
    event_id: Optional[int] = None,
    photo_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    detail: Optional[dict] = None,
) -> None:
    try:
        row = models.ActivityLog(
            action=action,
            event_id=event_id,
            photo_id=photo_id,
            ip_address=ip_address,
            detail=detail,
        )
        db.add(row)
        db.commit()
        logger.info(
            "%s event=%s photo=%s ip=%s detail=%s",
            action, event_id, photo_id, ip_address, detail,
        )
    except Exception:  # never let auditing break the request
        db.rollback()
        logger.exception("Failed to write activity log for %s", action)
