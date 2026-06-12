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
from ..services.folder_watcher import watcher_manager
from io import BytesIO

logger = logging.getLogger("wedfind.events")


def _owned_event_or_404(event_id: int, user: models.User, db: Session) -> models.Event:
    event = db.query(models.Event).filter(
        models.Event.id == event_id,
        models.Event.photographer_id == user.id,
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _validate_folder_path(raw: str) -> str:
    """Normalize + validate a local folder path. Reject traversal/non-dirs."""
    if not raw or "\x00" in raw:
        raise HTTPException(status_code=400, detail="Invalid folder path")
    path = os.path.abspath(os.path.normpath(raw))
    if not os.path.isabs(path):
        raise HTTPException(status_code=400, detail="Folder path must be absolute")
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Folder does not exist: {path}")
    return path


def _watch_response(watch: models.FolderWatch, db: Session) -> schemas.FolderWatchResponse:
    count = db.query(models.Photo.id).filter(models.Photo.event_id == watch.event_id).count()
    return schemas.FolderWatchResponse(
        id=watch.id, event_id=watch.event_id, folder_path=watch.folder_path,
        enabled=watch.enabled, created_at=watch.created_at, last_scan_at=watch.last_scan_at,
        watching=watcher_manager.is_watching(watch.id), photo_count=count,
    )

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

    # Stop + remove any folder watch (no FK cascade → must delete explicitly).
    watch = db.query(models.FolderWatch).filter(models.FolderWatch.event_id == event_id).first()
    if watch:
        watcher_manager.stop(watch.id)
        db.delete(watch)

    db.delete(event)
    db.commit()

    # Best-effort S3 cleanup (don't fail the request if a delete errors).
    for key in s3_keys:
        try:
            s3_service.delete_file(key)
        except Exception:
            logger.exception("S3 cleanup failed for key=%s (event_id=%s)", key, event_id)

    return None


# ---------------------- Folder watch (auto-upload) ----------------------

@router.post("/{event_id}/watch-folder", response_model=schemas.FolderWatchResponse)
def set_watch_folder(
    event_id: int,
    body: schemas.FolderWatchCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio),
):
    """Select/replace the watched folder for an event and start watching."""
    _owned_event_or_404(event_id, current_user, db)
    folder = _validate_folder_path(body.folder_path)

    watch = db.query(models.FolderWatch).filter(models.FolderWatch.event_id == event_id).first()
    if watch:
        # Folder changed → restart observer.
        watcher_manager.stop(watch.id)
        watch.folder_path = folder
        watch.enabled = True
    else:
        watch = models.FolderWatch(event_id=event_id, folder_path=folder, enabled=True)
        db.add(watch)
    db.commit()
    db.refresh(watch)

    watcher_manager.start(watch)
    db.refresh(watch)
    logger.info("WATCH_FOLDER_SET event=%s folder=%s by=%s", event_id, folder, current_user.id)
    return _watch_response(watch, db)


@router.get("/{event_id}/watch-folder", response_model=schemas.FolderWatchResponse)
def get_watch_folder(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio),
):
    _owned_event_or_404(event_id, current_user, db)
    watch = db.query(models.FolderWatch).filter(models.FolderWatch.event_id == event_id).first()
    if not watch:
        raise HTTPException(status_code=404, detail="No folder is being watched for this event")
    return _watch_response(watch, db)


@router.delete("/{event_id}/watch-folder", status_code=status.HTTP_204_NO_CONTENT)
def stop_watch_folder(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio),
):
    """Stop watching and remove the folder watch."""
    _owned_event_or_404(event_id, current_user, db)
    watch = db.query(models.FolderWatch).filter(models.FolderWatch.event_id == event_id).first()
    if not watch:
        raise HTTPException(status_code=404, detail="No folder is being watched for this event")
    watcher_manager.stop(watch.id)
    db.delete(watch)
    db.commit()
    logger.info("WATCH_FOLDER_STOP event=%s by=%s", event_id, current_user.id)
    return None


@router.post("/{event_id}/rescan", response_model=schemas.RescanResponse)
def rescan_folder(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio),
):
    """Manually scan the watched folder now (ingest any new files)."""
    _owned_event_or_404(event_id, current_user, db)
    watch = db.query(models.FolderWatch).filter(models.FolderWatch.event_id == event_id).first()
    if not watch:
        raise HTTPException(status_code=404, detail="No folder is being watched for this event")
    if not os.path.isdir(watch.folder_path):
        raise HTTPException(status_code=400, detail=f"Folder no longer exists: {watch.folder_path}")
    uploaded = watcher_manager.scan(watch.id, event_id, watch.folder_path)
    return schemas.RescanResponse(uploaded=uploaded)
