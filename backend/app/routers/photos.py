from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
import shutil
import logging
from ..database import get_db
from ..models import models
from ..schemas import schemas
from .deps import get_current_user
from ..services.face_processing import process_photo_faces
from ..services.s3_service import s3_service

router = APIRouter()
logger = logging.getLogger("wedfind.photos")

MAX_FILE_SIZE = 10 * 1024 * 1024 # 10MB
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/jpg"]

@router.post("/upload/{event_id}", response_model=List[schemas.PhotoResponse])
async def upload_photos(
    event_id: int,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    event = db.query(models.Event).filter(
        models.Event.id == event_id,
        models.Event.photographer_id == current_user.id
    ).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    db_photos = []
    skipped = []
    for file in files:
        logger.info("PHOTO_UPLOAD_START event=%s filename=%s mime=%s",
                    event_id, file.filename, file.content_type)

        # 1. Validate MIME type
        if file.content_type not in ALLOWED_MIME_TYPES:
            logger.warning("PHOTO_UPLOAD_SKIPPED (bad mime) filename=%s mime=%s",
                           file.filename, file.content_type)
            skipped.append({"filename": file.filename, "reason": "invalid type"})
            continue

        # 2. Validate Size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        if file_size > MAX_FILE_SIZE:
            logger.warning("PHOTO_UPLOAD_SKIPPED (too large) filename=%s size=%s",
                           file.filename, file_size)
            skipped.append({"filename": file.filename, "reason": "exceeds 10MB"})
            continue

        file_ext = file.filename.split(".")[-1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_ext}"

        # S3 Storage Key
        s3_key = f"events/{event_id}/{unique_filename}"

        # Upload to S3 — NO silent skip. A storage failure must be surfaced,
        # not hidden (previous `continue` dropped photos with HTTP 200).
        success = s3_service.upload_file(file.file, s3_key, file.content_type)
        if not success:
            logger.error("PHOTO_UPLOAD_FAILED event=%s filename=%s key=%s (see wedfind.s3 log for traceback)",
                         event_id, file.filename, s3_key)
            raise HTTPException(
                status_code=502,
                detail=f"Failed to upload '{file.filename}' to storage. No photos were saved past this point.",
            )

        logger.info("PHOTO_UPLOAD_SUCCESS event=%s filename=%s key=%s",
                    event_id, file.filename, s3_key)

        db_photo = models.Photo(
            event_id=event_id,
            filename=file.filename,
            filepath=s3_key, # Use S3 key as filepath reference
            storage_provider="s3",
            storage_key=s3_key,
            processing_status=models.ProcessingStatus.PENDING
        )
        db.add(db_photo)
        db.commit()
        db.refresh(db_photo)
        
        # Generate URL for response
        db_photo.url = s3_service.generate_presigned_url(s3_key)
        db_photos.append(db_photo)
        
        background_tasks.add_task(process_photo_faces, db_photo.id)
        
    return db_photos

@router.get("/event/{event_id}", response_model=List[schemas.PhotoResponse])
def get_event_photos(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
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
            photo.url = s3_service.generate_presigned_url(photo.storage_key)
        else:
            # Fallback for local files
            photo.url = f"/uploads/{photo.filepath.replace('../uploads/', '')}"
            
    return photos
