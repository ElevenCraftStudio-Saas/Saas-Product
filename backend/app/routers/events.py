from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import models
from ..schemas import schemas
from .deps import get_current_studio
from ..utils.qr import generate_qr_code
import uuid
import re
import os
import logging

from ..services.s3_service import s3_service
from io import BytesIO

logger = logging.getLogger("wedfind.events")

router = APIRouter()

def slugify(text: str):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text

@router.post("/", response_model=schemas.EventResponse)
def create_event(
    event_in: schemas.EventCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio)
):
    slug = f"{slugify(event_in.title)}-{str(uuid.uuid4())[:8]}"
    
    # Generate QR Code URL
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    event_url = f"{frontend_url}/event/{slug}"
    
    # Generate QR to memory
    import qrcode
    logger.info("QR_GENERATION_START slug=%s url=%s", slug, event_url)
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(event_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    logger.info("QR_GENERATION_SUCCESS slug=%s bytes=%s", slug, img_byte_arr.getbuffer().nbytes)

    s3_key = f"qr/{slug}_qr.png"
    logger.info("QR_UPLOAD_START slug=%s key=%s", slug, s3_key)
    qr_ok = s3_service.upload_file(img_byte_arr, s3_key, "image/png")
    if not qr_ok:
        # Don't pretend success — a presigned URL would point at a missing object.
        logger.error("QR_UPLOAD_FAILED slug=%s key=%s", slug, s3_key)
        raise HTTPException(status_code=502, detail="Failed to generate event QR (storage upload failed).")
    logger.info("QR_UPLOAD_SUCCESS slug=%s key=%s", slug, s3_key)
    
    db_event = models.Event(
        **event_in.model_dump(),
        event_slug=slug,
        qr_code_path=s3_key,
        storage_provider="s3",
        storage_key=s3_key,
        photographer_id=current_user.id
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    db_event.url = s3_service.generate_presigned_url(s3_key)
    return db_event

@router.get("/", response_model=List[schemas.EventResponse])
def get_events(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio)
):
    events = db.query(models.Event).filter(models.Event.photographer_id == current_user.id).all()
    for event in events:
        if event.storage_provider == "s3":
            event.url = s3_service.generate_presigned_url(event.storage_key)
        else:
            event.url = f"/uploads/{event.qr_code_path.replace('../uploads/', '')}"
    return events

@router.get("/{event_id}", response_model=schemas.EventResponse)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio)
):
    event = db.query(models.Event).filter(
        models.Event.id == event_id,
        models.Event.photographer_id == current_user.id
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if event.storage_provider == "s3":
        event.url = s3_service.generate_presigned_url(event.storage_key)
    else:
        event.url = f"/uploads/{event.qr_code_path.replace('../uploads/', '')}"
        
    return event

@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio)
):
    event = db.query(models.Event).filter(
        models.Event.id == event_id,
        models.Event.photographer_id == current_user.id
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Collect S3 keys (QR + all event photos) BEFORE the cascade delete.
    s3_keys = []
    if event.storage_provider == "s3" and event.storage_key:
        s3_keys.append(event.storage_key)
    for photo in event.photos:
        if photo.storage_provider == "s3" and photo.storage_key:
            s3_keys.append(photo.storage_key)

    db.delete(event)
    db.commit()

    # Best-effort S3 cleanup (don't fail the request if a delete errors).
    for key in s3_keys:
        try:
            s3_service.delete_file(key)
        except Exception:
            logger.exception("S3 cleanup failed for key=%s (event_id=%s)", key, event_id)

    return None
