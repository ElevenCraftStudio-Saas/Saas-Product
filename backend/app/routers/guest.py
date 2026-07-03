"""Guest flow (no login — consent-gated).

GET  /api/guest/{slug}                             -> event details (+ EVENT_VIEWED)
POST /api/guest/{slug}/selfie                      -> consent + face match (event-scoped)
GET  /api/guest/{slug}/photos/{photo_id}/download  -> signed url (event-isolated)
GET  /api/guest/{slug}/processing-stream           -> SSE: real-time selfie processing updates
"""
import os
import io
import uuid
import zipfile
import json
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..config import settings
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
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", 0.6))
CONSENT_VERSION = os.getenv("CONSENT_VERSION", "1.0")
DEFAULT_CONSENT_TEXT = (
    "I consent to face recognition processing for the purpose of finding my event photos."
)
MAX_SELFIE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIME = {"image/jpeg", "image/png"}
DOWNLOAD_URL_TTL = 3600  # seconds

# In-memory processing state for SSE (use Redis in production for multi-instance)
_processing_state: dict[str, dict] = {}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _photo_url(photo: models.Photo, thumb: bool = False) -> str:
    if photo.storage_provider == "s3":
        key = (photo.thumb_key or photo.storage_key) if thumb else photo.storage_key
        return s3_service.generate_presigned_url(key, DOWNLOAD_URL_TTL) or ""
    return settings.upload_url_for(photo.filepath)


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
        event.url = settings.upload_url_for(event.qr_code_path)

    activity.log_activity(
        db, activity.EVENT_VIEWED, event_id=event.id, ip_address=_client_ip(request)
    )
    return event


@router.get("/{slug}/processing-stream")
async def processing_stream(slug: str, request_id: str, request: Request):
    """SSE endpoint for real-time selfie processing updates.

    Client sends request_id in query param, receives progress events.
    """
    async def event_generator():
        try:
            # Send initial state
            state = _processing_state.get(request_id, {})
            if state:
                yield f"data: {json.dumps(state)}\n\n"

            # Stream updates until completion or timeout
            timeout = 60  # 60 seconds max
            start = asyncio.get_event_loop().time()

            while True:
                if asyncio.get_event_loop().time() - start > timeout:
                    yield f"data: {json.dumps({'type': 'timeout'})}\n\n"
                    break

                state = _processing_state.get(request_id, {})
                if state:
                    yield f"data: {json.dumps(state)}\n\n"

                if state.get("status") == "completed":
                    break

                await asyncio.sleep(0.5)  # Poll every 500ms

            # Clean up completed state
            _processing_state.pop(request_id, None)

        except asyncio.CancelledError:
            logger.debug("SSE client disconnected for request_id=%s", request_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{slug}/selfie")
@limiter.limit("10/minute")
async def match_selfie(
    slug: str,
    request: Request,
    file: UploadFile = File(...),
    consent: bool = Form(...),
    request_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """Process selfie with real-time progress via SSE.

    Returns request_id immediately, processes in background.
    Client connects to /{slug}/processing-stream?request_id={id} for updates.
    """
    event = _get_event_or_404(slug, db)
    ip = _client_ip(request)

    # Initialize processing state
    _processing_state[request_id] = {
        "type": "progress",
        "status": "starting",
        "message": "Initializing...",
        "progress": 0,
    }

    async def process_selfie_background():
        try:
            # Update state: validating
            _processing_state[request_id] = {
                "type": "progress",
                "status": "validating",
                "message": "Validating consent and file...",
                "progress": 10,
            }

            # 1. Consent validation
            if not consent:
                _processing_state[request_id] = {
                    "type": "error",
                    "status": "error",
                    "message": "Consent is required",
                }
                return

            # 2. File validation
            if file.content_type not in ALLOWED_MIME:
                _processing_state[request_id] = {
                    "type": "error",
                    "status": "error",
                    "message": "Only JPEG or PNG images are allowed",
                }
                return

            contents = await file.read()
            if len(contents) == 0:
                _processing_state[request_id] = {
                    "type": "error",
                    "status": "error",
                    "message": "Empty file",
                }
                return
            if len(contents) > MAX_SELFIE_BYTES:
                _processing_state[request_id] = {
                    "type": "error",
                    "status": "error",
                    "message": "Image exceeds 10 MB limit",
                }
                return

            # Update state: recording consent
            _processing_state[request_id] = {
                "type": "progress",
                "status": "consenting",
                "message": "Recording consent...",
                "progress": 20,
            }

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

            # Update state: saving file
            _processing_state[request_id] = {
                "type": "progress",
                "status": "uploading",
                "message": "Saving selfie...",
                "progress": 30,
            }

            # Persist selfie to temp file
            temp_dir = os.path.join(settings.UPLOAD_DIR, "temp_selfies")
            os.makedirs(temp_dir, exist_ok=True)
            safe_name = os.path.basename(file.filename or "selfie")
            temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{safe_name}")
            with open(temp_path, "wb") as buffer:
                buffer.write(contents)

            try:
                # Update state: detecting faces
                _processing_state[request_id] = {
                    "type": "progress",
                    "status": "detecting",
                    "message": "Detecting faces in selfie...",
                    "progress": 50,
                }

                activity.log_activity(
                    db, activity.SELFIE_UPLOADED, event_id=event.id, ip_address=ip,
                    detail={"size": len(contents), "mime": file.content_type},
                )

                # Face detection
                faces = await run_in_threadpool(face_engine.get_faces, temp_path)
                if not faces:
                    _processing_state[request_id] = {
                        "type": "error",
                        "status": "error",
                        "message": "No face detected in selfie",
                    }
                    return
                if len(faces) > 1:
                    _processing_state[request_id] = {
                        "type": "error",
                        "status": "error",
                        "message": "Multiple faces detected. Please use a selfie with only your face",
                    }
                    return

                # Update state: matching
                _processing_state[request_id] = {
                    "type": "progress",
                    "status": "matching",
                    "message": "Matching your face to event photos...",
                    "progress": 70,
                }

                guest_embedding = faces[0].embedding
                matched_ids = match_event(db, event.id, guest_embedding, MATCH_THRESHOLD)

                from ..core.metrics import selfie_matches_total
                selfie_matches_total.labels("yes" if matched_ids else "no").inc()

                matched_photos = (
                    db.query(models.Photo).filter(models.Photo.id.in_(matched_ids)).all()
                    if matched_ids else []
                )

                result = [
                    schemas.GuestPhoto(id=p.id, filename=p.filename, url=_photo_url(p, thumb=True))
                    for p in matched_photos
                ]

                # Update state: completed
                _processing_state[request_id] = {
                    "type": "completed",
                    "status": "completed",
                    "message": f"Found {len(result)} matching photos",
                    "progress": 100,
                    "count": len(result),
                    "photos": [{"id": p.id, "filename": p.filename, "url": p.url} for p in result],
                }

                activity.log_activity(
                    db, activity.FACE_MATCH_COMPLETED, event_id=event.id, ip_address=ip,
                    detail={"matches": len(result)},
                )

            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        except Exception as e:
            logger.exception("Selfie processing failed for request_id=%s", request_id)
            _processing_state[request_id] = {
                "type": "error",
                "status": "error",
                "message": f"Processing failed: {str(e)}",
            }

    # Start background processing
    asyncio.create_task(process_selfie_background())

    # Return immediately with request_id
    return {
        "request_id": request_id,
        "message": "Processing started. Connect to processing stream for updates.",
    }


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
