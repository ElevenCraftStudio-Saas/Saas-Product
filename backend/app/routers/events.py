from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import models
from ..schemas import schemas
from .deps import require_admin, require_user
from ..utils.qr import generate_qr_code
import uuid
import re
import os
import logging

from ..services.s3_service import s3_service
from ..services.folder_watcher import watcher_manager
from ..services import retention
from ..core.limits import effective_event_limit
from ..core.metrics import quota_rejections_total
from fastapi.responses import StreamingResponse
from io import BytesIO, StringIO
import csv

logger = logging.getLogger("wedfind.events")


def _owned_event_or_404(event_id: int, user: models.User, db: Session) -> models.Event:
    event = db.query(models.Event).filter(
        models.Event.id == event_id,
        models.Event.photographer_id == user.id,
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _event_or_404(event_id: int, db: Session) -> models.Event:
    """Look up an event by id without an owner filter (admin-gated routes)."""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
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
    current_user: models.User = Depends(require_user)
):
    count = db.query(models.Event.id).filter(
        models.Event.photographer_id == current_user.id
    ).count()
    limit = effective_event_limit(current_user)
    if count >= limit:
        quota_rejections_total.labels("event").inc()
        raise HTTPException(
            status_code=403,
            detail=f"Event limit reached ({count}/{limit}). Contact your admin to raise it.",
        )

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
    current_user: models.User = Depends(require_user)
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
    current_user: models.User = Depends(require_user)
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
    current_user: models.User = Depends(require_user)
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

    # Stop + remove ALL folder watches (no FK cascade → must delete explicitly).
    watches = db.query(models.FolderWatch).filter(models.FolderWatch.event_id == event_id).all()
    for watch in watches:
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


# ---------------------- Folder watch (auto-upload, multiple folders) ----------------------
# An event can watch MANY folders (e.g. one per photographer/cameraman). Each
# FolderWatch row is one folder; the watcher_manager keys observers by watch id.

def _watch_or_404(event_id: int, watch_id: int, db: Session) -> models.FolderWatch:
    _event_or_404(event_id, db)
    watch = db.query(models.FolderWatch).filter(
        models.FolderWatch.id == watch_id,
        models.FolderWatch.event_id == event_id,
    ).first()
    if not watch:
        raise HTTPException(status_code=404, detail="Folder watch not found")
    return watch


@router.post("/{event_id}/watch-folders", response_model=schemas.FolderWatchResponse)
def add_watch_folder(
    event_id: int,
    body: schemas.FolderWatchCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """Add a folder to watch for this event and start watching it."""
    _event_or_404(event_id, db)
    folder = _validate_folder_path(body.folder_path)

    existing = db.query(models.FolderWatch).filter(
        models.FolderWatch.event_id == event_id,
        models.FolderWatch.folder_path == folder,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="This folder is already being watched for this event")

    watch = models.FolderWatch(event_id=event_id, folder_path=folder, enabled=True)
    db.add(watch)
    db.commit()
    db.refresh(watch)

    watcher_manager.start(watch)
    db.refresh(watch)
    logger.info("WATCH_FOLDER_ADD event=%s folder=%s by=%s", event_id, folder, current_user.id)
    return _watch_response(watch, db)


@router.get("/{event_id}/watch-folders", response_model=List[schemas.FolderWatchResponse])
def list_watch_folders(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    _event_or_404(event_id, db)
    watches = (
        db.query(models.FolderWatch)
        .filter(models.FolderWatch.event_id == event_id)
        .order_by(models.FolderWatch.created_at.asc())
        .all()
    )
    return [_watch_response(w, db) for w in watches]


@router.delete("/{event_id}/watch-folders/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_watch_folder(
    event_id: int,
    watch_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """Stop watching one folder and remove it."""
    watch = _watch_or_404(event_id, watch_id, db)
    watcher_manager.stop(watch.id)
    db.delete(watch)
    db.commit()
    logger.info("WATCH_FOLDER_REMOVE event=%s watch=%s by=%s", event_id, watch_id, current_user.id)
    return None


@router.post("/{event_id}/watch-folders/{watch_id}/rescan", response_model=schemas.RescanResponse)
def rescan_watch_folder(
    event_id: int,
    watch_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """Manually rescan one watched folder now."""
    watch = _watch_or_404(event_id, watch_id, db)
    if not os.path.isdir(watch.folder_path):
        raise HTTPException(status_code=400, detail=f"Folder no longer exists: {watch.folder_path}")
    uploaded = watcher_manager.scan(watch.id, event_id, watch.folder_path)
    return schemas.RescanResponse(uploaded=uploaded)


@router.post("/{event_id}/rescan-all", response_model=schemas.RescanResponse)
def rescan_all_folders(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """Rescan every watched folder for this event."""
    _event_or_404(event_id, db)
    watches = db.query(models.FolderWatch).filter(models.FolderWatch.event_id == event_id).all()
    total = 0
    for w in watches:
        if os.path.isdir(w.folder_path):
            total += watcher_manager.scan(w.id, event_id, w.folder_path)
    return schemas.RescanResponse(uploaded=total)


# ---------------------- Privacy / DPDP ----------------------

def _privacy_summary(event: models.Event, db: Session) -> schemas.PrivacySummary:
    consent_count = db.query(models.GuestConsent.id).filter(
        models.GuestConsent.event_id == event.id
    ).count()
    photos_count = db.query(models.Photo.id).filter(
        models.Photo.event_id == event.id
    ).count()
    return schemas.PrivacySummary(
        event_id=event.id,
        consent_count=consent_count,
        photos_count=photos_count,
        retention_days=event.retention_days,
        scheduled_purge_at=retention.scheduled_purge_at(event),
    )


@router.get("/{event_id}/privacy", response_model=schemas.PrivacySummary)
def get_privacy(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    event = _event_or_404(event_id, db)
    return _privacy_summary(event, db)


@router.patch("/{event_id}/retention", response_model=schemas.PrivacySummary)
def set_retention(
    event_id: int,
    body: schemas.RetentionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    event = _event_or_404(event_id, db)
    if body.retention_days is not None and body.retention_days < 1:
        raise HTTPException(status_code=400, detail="retention_days must be >= 1 or null")
    event.retention_days = body.retention_days
    db.commit()
    db.refresh(event)
    logger.info("RETENTION_SET event=%s days=%s by=%s", event_id, body.retention_days, current_user.id)
    return _privacy_summary(event, db)


@router.get("/{event_id}/consents", response_model=List[schemas.ConsentRecord])
def list_consents(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    _event_or_404(event_id, db)
    return (
        db.query(models.GuestConsent)
        .filter(models.GuestConsent.event_id == event_id)
        .order_by(models.GuestConsent.consent_timestamp.desc())
        .all()
    )


@router.get("/{event_id}/consents/export")
def export_consents(
    event_id: int,
    format: str = "csv",
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """Download proof-of-consent ledger (CSV or PDF) for compliance/audit."""
    event = _event_or_404(event_id, db)
    rows = (
        db.query(models.GuestConsent)
        .filter(models.GuestConsent.event_id == event_id)
        .order_by(models.GuestConsent.consent_timestamp.asc())
        .all()
    )
    fmt = (format or "csv").lower()

    if fmt == "csv":
        sio = StringIO()
        w = csv.writer(sio)
        w.writerow(["id", "timestamp", "ip_address", "consent_version", "consent_text", "user_agent"])
        for r in rows:
            w.writerow([
                r.id, r.consent_timestamp, r.ip_address or "",
                r.consent_version or "", r.consent_text or "", r.user_agent or "",
            ])
        data = sio.getvalue().encode("utf-8")
        return StreamingResponse(
            BytesIO(data), media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="consents-event-{event_id}.csv"'},
        )

    if fmt == "pdf":
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ImportError:
            raise HTTPException(status_code=501, detail="PDF export unavailable (reportlab not installed).")
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        y = height - 50
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, f"Consent Ledger — {event.title}")
        y -= 20
        c.setFont("Helvetica", 8)
        c.drawString(50, y, f"Event #{event_id} · {len(rows)} consent record(s) · DPDP proof-of-consent")
        y -= 25
        c.setFont("Helvetica-Bold", 8)
        c.drawString(50, y, "Timestamp")
        c.drawString(210, y, "IP")
        c.drawString(310, y, "Version")
        c.drawString(370, y, "Consent text")
        y -= 14
        c.setFont("Helvetica", 7)
        for r in rows:
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 7)
            c.drawString(50, y, str(r.consent_timestamp)[:19])
            c.drawString(210, y, (r.ip_address or "")[:18])
            c.drawString(310, y, (r.consent_version or "")[:8])
            c.drawString(370, y, (r.consent_text or "")[:28])
            y -= 12
        c.save()
        buf.seek(0)
        return StreamingResponse(
            buf, media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="consents-event-{event_id}.pdf"'},
        )

    raise HTTPException(status_code=400, detail="format must be 'csv' or 'pdf'")
