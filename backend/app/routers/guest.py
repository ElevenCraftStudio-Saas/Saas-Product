"""Guest flow (no login — consent-gated).

GET  /api/guest/{slug}                             -> event details (+ EVENT_VIEWED)
POST /api/guest/{slug}/selfie                      -> consent + face match (event-scoped)
GET  /api/guest/{slug}/photos/{photo_id}/download  -> signed url (event-isolated)
"""
import os
import io
import uuid
import zipfile
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import models
from ..schemas import schemas
from ..services.face_engine import face_engine
from ..services.matching import match_event
from ..services.s3_service import s3_service
from ..services import activity
from ..core.limiter import limiter

router = APIRouter()
logger = logging.getLogger("wedfind.guest")

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "../uploads")
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", 0.6))
CONSENT_VERSION = os.getenv("CONSENT_VERSION", "1.0")
DEFAULT_CONSENT_TEXT = (
    "I consent to face recognition processing for the purpose of finding my event photos."
)
MAX_SELFIE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME = {"image/jpeg", "image/png"}
DOWNLOAD_URL_TTL = 3600  # seconds


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _photo_url(photo: models.Photo) -> str:
    if photo.storage_provider == "s3":
        return s3_service.generate_presigned_url(photo.storage_key, DOWNLOAD_URL_TTL) or ""
    return f"/uploads/{photo.filepath.replace('../uploads/', '')}"


def _get_event_or_404(slug: str, db: Session) -> models.Event:
    event = db.query(models.Event).filter(models.Event.event_slug == slug).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/{slug}", response_model=schemas.GuestEventResponse)
def get_public_event(slug: str, request: Request, db: Session = Depends(get_db)):
    event = _get_event_or_404(slug, db)

    if event.storage_provider == "s3":
        event.url = s3_service.generate_presigned_url(event.storage_key, DOWNLOAD_URL_TTL)
    elif event.qr_code_path:
        event.url = f"/uploads/{event.qr_code_path.replace('../uploads/', '')}"

    activity.log_activity(
        db, activity.EVENT_VIEWED, event_id=event.id, ip_address=_client_ip(request)
    )
    return event


@router.post("/{slug}/selfie", response_model=schemas.SelfieMatchResponse)
@limiter.limit("10/minute")
async def match_selfie(
    slug: str,
    request: Request,
    file: UploadFile = File(...),
    consent: bool = Form(...),
    db: Session = Depends(get_db),
):
    event = _get_event_or_404(slug, db)
    ip = _client_ip(request)

    # 1. Consent is mandatory before any biometric processing.
    if not consent:
        raise HTTPException(
            status_code=400,
            detail="Consent to face recognition processing is required.",
        )

    # 2. File validation.
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Only JPEG or PNG images are allowed.")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(contents) > MAX_SELFIE_BYTES:
        raise HTTPException(status_code=400, detail="Image exceeds the 10 MB limit.")

    # Record consent (server-captured IP + version + exact text + UA) before processing.
    db.add(
        models.GuestConsent(
            event_id=event.id,
            ip_address=ip,
            consent_version=CONSENT_VERSION,
            consent_text=event.consent_text or DEFAULT_CONSENT_TEXT,
            user_agent=(request.headers.get("user-agent") or "")[:512],
        )
    )
    db.commit()

    # 3. Persist selfie to a temp file for InsightFace.
    temp_dir = os.path.join(UPLOAD_DIR, "temp_selfies")
    os.makedirs(temp_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "selfie")
    temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{safe_name}")
    with open(temp_path, "wb") as buffer:
        buffer.write(contents)

    try:
        activity.log_activity(
            db, activity.SELFIE_UPLOADED, event_id=event.id, ip_address=ip,
            detail={"size": len(contents), "mime": file.content_type},
        )

        # 4. Exactly one face required.
        faces = face_engine.get_faces(temp_path)
        if not faces:
            raise HTTPException(status_code=400, detail="No face detected in the selfie.")
        if len(faces) > 1:
            raise HTTPException(
                status_code=400,
                detail="Multiple faces detected. Please upload a selfie with only your face.",
            )

        guest_embedding = faces[0].embedding

        # 5. Match — STRICTLY within this event only (pgvector on PG, else Python).
        matched_ids = match_event(db, event.id, guest_embedding, MATCH_THRESHOLD)
        matched_photos = (
            db.query(models.Photo).filter(models.Photo.id.in_(matched_ids)).all()
            if matched_ids else []
        )

        result = [
            schemas.GuestPhoto(id=p.id, filename=p.filename, url=_photo_url(p))
            for p in matched_photos
        ]

        activity.log_activity(
            db, activity.FACE_MATCH_COMPLETED, event_id=event.id, ip_address=ip,
            detail={"matches": len(result)},
        )

        return schemas.SelfieMatchResponse(count=len(result), photos=result)

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/{slug}/photos/{photo_id}/download", response_model=schemas.DownloadResponse)
def download_photo(slug: str, photo_id: int, request: Request, db: Session = Depends(get_db)):
    event = _get_event_or_404(slug, db)

    # Event isolation: the photo MUST belong to this event's slug.
    photo = (
        db.query(models.Photo)
        .filter(models.Photo.id == photo_id, models.Photo.event_id == event.id)
        .first()
    )
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found in this event.")

    url = _photo_url(photo)
    if not url:
        raise HTTPException(status_code=500, detail="Could not generate download URL.")

    ip = _client_ip(request)
    db.add(models.Download(photo_id=photo.id, ip_address=ip))
    db.commit()
    activity.log_activity(
        db, activity.PHOTO_DOWNLOADED, event_id=event.id, photo_id=photo.id, ip_address=ip
    )

    return schemas.DownloadResponse(url=url, expires_in=DOWNLOAD_URL_TTL)


@router.post("/{slug}/download-zip")
@limiter.limit("5/minute")
def download_zip(
    slug: str,
    request: Request,
    body: schemas.PhotoIdsRequest,
    db: Session = Depends(get_db),
):
    """Stream a ZIP of the requested photos (event-isolated)."""
    event = _get_event_or_404(slug, db)
    if not body.photo_ids:
        raise HTTPException(status_code=400, detail="No photos selected.")

    # Only photos that belong to THIS event are included (isolation).
    photos = (
        db.query(models.Photo)
        .filter(models.Photo.id.in_(body.photo_ids), models.Photo.event_id == event.id)
        .all()
    )
    if not photos:
        raise HTTPException(status_code=404, detail="No matching photos in this event.")

    ip = _client_ip(request)
    buf = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, photo in enumerate(photos, start=1):
            data = s3_service.get_bytes(photo.storage_key) if photo.storage_key else None
            if not data:
                logger.warning("ZIP skip missing key photo_id=%s", photo.id)
                continue
            # Prefix index to avoid duplicate filename collisions in the zip.
            zf.writestr(f"{i:03d}_{photo.filename}", data)
            db.add(models.Download(photo_id=photo.id, ip_address=ip))
            added += 1
    db.commit()

    if added == 0:
        raise HTTPException(status_code=502, detail="Could not retrieve any photos from storage.")

    activity.log_activity(
        db, activity.PHOTO_DOWNLOADED, event_id=event.id, ip_address=ip,
        detail={"zip": True, "count": added},
    )
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}-photos.zip"'},
    )


@router.post("/{slug}/erase", response_model=schemas.EraseResponse)
@limiter.limit("5/minute")
def erase_my_data(slug: str, request: Request, db: Session = Depends(get_db)):
    """DPDP right-to-erasure: delete this caller's data for this event.

    Guest data = consent records + download logs + activity logs keyed by the
    caller's IP within this event. (Selfies/face embeddings are never stored.)
    """
    event = _get_event_or_404(slug, db)
    ip = _client_ip(request)

    consents_deleted = (
        db.query(models.GuestConsent)
        .filter(models.GuestConsent.event_id == event.id, models.GuestConsent.ip_address == ip)
        .delete(synchronize_session=False)
    )

    # Downloads for this IP, scoped to photos in this event.
    event_photo_ids = [
        pid for (pid,) in db.query(models.Photo.id).filter(models.Photo.event_id == event.id).all()
    ]
    downloads_deleted = 0
    if event_photo_ids:
        downloads_deleted = (
            db.query(models.Download)
            .filter(
                models.Download.ip_address == ip,
                models.Download.photo_id.in_(event_photo_ids),
            )
            .delete(synchronize_session=False)
        )

    activity_deleted = (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.event_id == event.id, models.ActivityLog.ip_address == ip)
        .delete(synchronize_session=False)
    )
    db.commit()

    activity.log_activity(
        db, activity.DATA_ERASED, event_id=event.id, ip_address=ip,
        detail={"consents": consents_deleted, "downloads": downloads_deleted, "activity": activity_deleted},
    )
    return schemas.EraseResponse(
        consents_deleted=consents_deleted,
        downloads_deleted=downloads_deleted,
        activity_deleted=activity_deleted,
    )
