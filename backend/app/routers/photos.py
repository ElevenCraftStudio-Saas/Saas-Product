from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import logging
from ..config import settings
from ..database import get_db
from ..models import models
from ..schemas import schemas
from .deps import require_user
from ..services.dispatch import enqueue_process_photo, enqueue_make_thumbnail
from ..services.s3_service import s3_service
from ..services.photo_ingest import ingest_photo_bytes, is_allowed_image, MAX_FILE_SIZE

router = APIRouter()
logger = logging.getLogger("wedfind.photos")

@router.post("/upload/{event_id}", response_model=List[schemas.PhotoResponse])
async def upload_photos(
    event_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_user)
):
    event = db.query(models.Event).filter(
        models.Event.id == event_id,
        models.Event.photographer_id == current_user.id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    db_photos = []
    for file in files:
        logger.info("PHOTO_UPLOAD_START event=%s filename=%s mime=%s",
                    event_id, file.filename, file.content_type)

        if not is_allowed_image(file.filename or ""):
            logger.warning("PHOTO_UPLOAD_SKIPPED (bad type) filename=%s", file.filename)
            continue

        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            logger.warning("PHOTO_UPLOAD_SKIPPED (too large) filename=%s size=%s",
                           file.filename, len(content))
            continue

        # Reuse the shared ingest pipeline (S3 + DB) — single source of truth.
        try:
            db_photo = ingest_photo_bytes(db, event_id, file.filename, content, file.content_type)
        except RuntimeError as e:
            logger.error("PHOTO_UPLOAD_FAILED event=%s filename=%s: %s", event_id, file.filename, e)
            raise HTTPException(status_code=502, detail=f"Failed to upload '{file.filename}' to storage.")
        except ValueError as e:
            logger.warning("PHOTO_UPLOAD_SKIPPED filename=%s: %s", file.filename, e)
            continue

        logger.info("PHOTO_UPLOAD_SUCCESS event=%s filename=%s key=%s",
                    event_id, file.filename, db_photo.storage_key)
        db_photo.url = s3_service.generate_presigned_url(db_photo.storage_key)
        db_photos.append(db_photo)
        enqueue_process_photo(db_photo.id, background_tasks)
        enqueue_make_thumbnail(db_photo.id, background_tasks)

    return db_photos

@router.get("/event/{event_id}", response_model=List[schemas.PhotoResponse])
def get_event_photos(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_user)
):
    event = db.query(models.Event).filter(
        models.Event.id == event_id,
        models.Event.photographer_id == current_user.id
    ).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    photos = db.query(models.Photo).filter(models.Photo.event_id == event_id).all()
    
    for photo in photos:
        if photo.storage_provider == "s3":
            # Serve the thumbnail in the grid; the original is fetched on download.
            photo.url = s3_service.generate_presigned_url(photo.thumb_key or photo.storage_key)
        else:
            # Fallback for local files
            photo.url = settings.upload_url_for(photo.filepath)
            
    return photos
