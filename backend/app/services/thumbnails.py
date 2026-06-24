"""Thumbnail generation: 400px WebP derived from the S3 original."""
import io
import uuid
import logging

from PIL import Image, ImageOps

from ..database import SessionLocal
from ..models import models
from .s3_service import s3_service
from ..core.metrics import thumbnails_total

logger = logging.getLogger("wedfind.thumb")

THUMB_MAX = 400  # longest edge, px


def make_thumbnail_for_photo(photo_id: int) -> bool:
    """Generate + store a thumbnail for a photo. Idempotent (overwrites key).
    Returns True on success. Swallows + logs errors (caller may retry)."""
    db = SessionLocal()
    try:
        photo = db.query(models.Photo).filter(models.Photo.id == photo_id).first()
        if not photo or not photo.storage_key:
            return False
        data = s3_service.get_bytes(photo.storage_key)
        if not data:
            return False

        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        img.thumbnail((THUMB_MAX, THUMB_MAX))
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=80)
        buf.seek(0)

        key = f"events/{photo.event_id}/thumbs/{uuid.uuid4()}.webp"
        if not s3_service.upload_file(buf, key, "image/webp"):
            thumbnails_total.labels("fail").inc()
            return False
        photo.thumb_key = key
        db.commit()
        thumbnails_total.labels("ok").inc()
        return True
    except Exception:
        logger.exception("Thumbnail failed for photo %s", photo_id)
        thumbnails_total.labels("fail").inc()
        db.rollback()
        return False
    finally:
        db.close()
