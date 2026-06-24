"""Reusable photo ingestion — single source of truth for the upload pipeline.

Both the manual upload route (photos.py) and the folder watcher
(folder_watcher.py) call this. No duplicated S3/DB logic.
"""
import io
import os
import uuid
import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import models
from .s3_service import s3_service
from ..core.limits import effective_storage_limit_mb, user_storage_used_bytes

logger = logging.getLogger("wedfind.ingest")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB (originals can be large)


def is_allowed_image(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXT


def photo_exists(db: Session, event_id: int, filename: str) -> bool:
    """Dedup: a photo with this original filename already ingested for the event."""
    return (
        db.query(models.Photo.id)
        .filter(models.Photo.event_id == event_id, models.Photo.filename == filename)
        .first()
        is not None
    )


def ingest_photo_bytes(
    db: Session,
    event_id: int,
    filename: str,
    content: bytes,
    content_type: str | None = None,
) -> models.Photo:
    """Upload bytes to S3 + create the Photo row. Raises on failure.

    Caller is responsible for triggering embedding generation with the
    returned photo.id (route uses BackgroundTasks; watcher uses a thread).
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise ValueError(f"Unsupported file type: {filename}")
    if len(content) == 0:
        raise ValueError(f"Empty file: {filename}")
    if len(content) > MAX_FILE_SIZE:
        raise ValueError(f"File exceeds {MAX_FILE_SIZE} bytes: {filename}")

    # Storage quota: enforce against the event owner BEFORE the S3 upload so a
    # rejected upload never leaves an orphan object.
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    owner = (
        db.query(models.User).filter(models.User.id == event.photographer_id).first()
        if event is not None else None
    )
    if owner is not None:
        limit_bytes = effective_storage_limit_mb(owner) * 1024 * 1024
        used = user_storage_used_bytes(db, owner)
        if used + len(content) > limit_bytes:
            raise HTTPException(
                status_code=403,
                detail="Storage limit reached. Contact your admin to raise it.",
            )

    ct = content_type or MIME_BY_EXT.get(ext, "application/octet-stream")
    s3_key = f"events/{event_id}/{uuid.uuid4()}{ext}"

    if not s3_service.upload_file(io.BytesIO(content), s3_key, ct):
        raise RuntimeError(f"S3 upload failed for {filename} (key={s3_key})")

    photo = models.Photo(
        event_id=event_id,
        filename=filename,
        filepath=s3_key,
        storage_provider="s3",
        storage_key=s3_key,
        processing_status=models.ProcessingStatus.PENDING,
        size_bytes=len(content),
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    logger.info(
        "PHOTO_INGEST_OK event=%s file=%s key=%s photo_id=%s bytes=%s",
        event_id, filename, s3_key, photo.id, len(content),
    )
    return photo
