"""Guest flow (no login — consent-gated).

GET  /api/guest/{slug}                             -> event details (+ EVENT_VIEWED)
POST /api/guest/{slug}/selfie                      -> consent + face match (event-scoped)
GET  /api/guest/{slug}/photos/{photo_id}/download  -> signed url (event-isolated)
GET  /api/guest/{slug}/processing-stream           -> SSE: real-time selfie processing updates
"""
import os
import io
import time
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
from ..database import get_db, SessionLocal
from ..models import models
from ..schemas import schemas
from ..services.face_engine import face_engine
from ..services.matching import match_event
from ..services.s3_service import s3_service
from ..services import activity
from ..core.limiter import limiter
from ..core import signing

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

# In-memory processing state for SSE (single-process only — gunicorn runs -w 1;
# move to Redis before scaling web replicas). Entries are (state, monotonic ts)
# and are lazily evicted after STATE_TTL_SECONDS so clients that never connect
# can't grow the dict forever.
STATE_TTL_SECONDS = 600
_processing_state: dict[str, tuple[dict, float]] = {}


def _evict_stale() -> None:
    now = time.monotonic()
    for key in [k for k, (_, ts) in _processing_state.items() if now - ts > STATE_TTL_SECONDS]:
        _processing_state.pop(key, None)


def _state_put(request_id: str, state: dict) -> None:
    _evict_stale()
    _processing_state[request_id] = (state, time.monotonic())


def _state_get(request_id: str) -> dict | None:
    item = _processing_state.get(request_id)
    return item[0] if item else None


def _state_pop(request_id: str) -> None:
    _processing_state.pop(request_id, None)


def _require_uuid(request_id: str) -> str:
    """Guests must use unguessable request ids — a guessable id would let one
    guest subscribe to another's processing stream (which carries presigned
    photo URLs)."""
    try:
        return str(uuid.UUID(request_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=422, detail="request_id must be a UUID")


def _client_ip(request: Request) -> str:
    # Deliberately NOT reading X-Forwarded-For here: the header is client-
    # spoofable and this IP is the identity for consent records and the
    # right-to-erasure scope. Behind the proxy, gunicorn/uvicorn rewrites
    # request.client from Forwarded headers per FORWARDED_ALLOW_IPS.
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
@limiter.limit("30/minute")
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

    Client sends its (UUID) request_id in a query param, receives progress
    frames. The stream ends on a terminal state (completed/error), after 10s
    with no state at all (client connected before/without a selfie POST), or
    at the 60s hard cap.
    """
    request_id = _require_uuid(request_id)

    async def event_generator():
        timeout = 60          # hard cap
        empty_grace = 10      # end early if no state ever shows up
        start = asyncio.get_event_loop().time()
        last_sent: str | None = None
        try:
            while True:
                elapsed = asyncio.get_event_loop().time() - start
                if elapsed > timeout:
                    yield f"data: {json.dumps({'type': 'timeout'})}\n\n"
                    break

                state = _state_get(request_id)
                if state is None:
                    if last_sent is None and elapsed > empty_grace:
                        yield f"data: {json.dumps({'type': 'timeout'})}\n\n"
                        break
                else:
                    frame = json.dumps(state)
                    if frame != last_sent:
                        yield f"data: {frame}\n\n"
                        last_sent = frame
                    if state.get("status") in ("completed", "error"):
                        break

                await asyncio.sleep(0.5)  # Poll every 500ms

            # Terminal state delivered (or timed out) — drop it.
            _state_pop(request_id)

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
    request_id = _require_uuid(request_id)
    event = _get_event_or_404(slug, db)
    event_id, event_consent_text = event.id, event.consent_text

    # Everything the background task needs is captured NOW — the request-scoped
    # db session, UploadFile and Request all die once this handler returns.
    ip = _client_ip(request)
    user_agent = (request.headers.get("user-agent") or "")[:512]
    content_type = file.content_type
    filename = os.path.basename(file.filename or "selfie")

    _state_put(request_id, {
        "type": "progress",
        "status": "validating",
        "message": "Validating consent and file...",
        "progress": 10,
    })

    # Cheap validations happen inline; errors still surface via SSE so the
    # client contract (200 + stream) is unchanged.
    if not consent:
        _state_put(request_id, {
            "type": "error", "status": "error", "message": "Consent is required",
        })
        return {"request_id": request_id, "message": "Processing started."}

    if content_type not in ALLOWED_MIME:
        _state_put(request_id, {
            "type": "error", "status": "error",
            "message": "Only JPEG or PNG images are allowed",
        })
        return {"request_id": request_id, "message": "Processing started."}

    contents = await file.read()
    if len(contents) == 0:
        _state_put(request_id, {
            "type": "error", "status": "error", "message": "Empty file",
        })
        return {"request_id": request_id, "message": "Processing started."}
    if len(contents) > MAX_SELFIE_BYTES:
        _state_put(request_id, {
            "type": "error", "status": "error",
            "message": "Image exceeds 10 MB limit",
        })
        return {"request_id": request_id, "message": "Processing started."}

    async def process_selfie_background():
        # Own session: the request's Depends(get_db) session is closed by the
        # time this task runs.
        task_db = SessionLocal()
        try:
            _state_put(request_id, {
                "type": "progress",
                "status": "consenting",
                "message": "Recording consent...",
                "progress": 20,
            })

            task_db.add(
                models.GuestConsent(
                    event_id=event_id,
                    ip_address=ip,
                    consent_version=CONSENT_VERSION,
                    consent_text=event_consent_text or DEFAULT_CONSENT_TEXT,
                    user_agent=user_agent,
                )
            )
            task_db.commit()

            _state_put(request_id, {
                "type": "progress",
                "status": "uploading",
                "message": "Saving selfie...",
                "progress": 30,
            })

            # Persist selfie to temp file
            temp_dir = os.path.join(settings.UPLOAD_DIR, "temp_selfies")
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{filename}")
            with open(temp_path, "wb") as buffer:
                buffer.write(contents)

            try:
                _state_put(request_id, {
                    "type": "progress",
                    "status": "detecting",
                    "message": "Detecting faces in selfie...",
                    "progress": 50,
                })

                activity.log_activity(
                    task_db, activity.SELFIE_UPLOADED, event_id=event_id, ip_address=ip,
                    detail={"size": len(contents), "mime": content_type},
                )

                # Face detection
                faces = await run_in_threadpool(face_engine.get_faces, temp_path)
                if not faces:
                    _state_put(request_id, {
                        "type": "error", "status": "error",
                        "message": "No face detected in selfie",
                    })
                    return
                if len(faces) > 1:
                    _state_put(request_id, {
                        "type": "error", "status": "error",
                        "message": "Multiple faces detected. Please use a selfie with only your face",
                    })
                    return

                _state_put(request_id, {
                    "type": "progress",
                    "status": "matching",
                    "message": "Matching your face to event photos...",
                    "progress": 70,
                })

                guest_embedding = faces[0].embedding
                matched_ids = match_event(task_db, event_id, guest_embedding, MATCH_THRESHOLD)

                from ..core.metrics import selfie_matches_total
                selfie_matches_total.labels("yes" if matched_ids else "no").inc()

                matched_photos = (
                    task_db.query(models.Photo).filter(models.Photo.id.in_(matched_ids)).all()
                    if matched_ids else []
                )

                # Each matched photo gets a signed download token — the ONLY
                # way to use the download endpoints (anti-scraping).
                result = [
                    schemas.GuestPhoto(
                        id=p.id,
                        filename=p.filename,
                        url=_photo_url(p, thumb=True),
                        download_token=signing.sign_download(event_id, p.id),
                    )
                    for p in matched_photos
                ]

                _state_put(request_id, {
                    "type": "completed",
                    "status": "completed",
                    "message": f"Found {len(result)} matching photos",
                    "progress": 100,
                    "count": len(result),
                    "photos": [
                        {
                            "id": p.id,
                            "filename": p.filename,
                            "url": p.url,
                            "download_token": p.download_token,
                        }
                        for p in result
                    ],
                })

                activity.log_activity(
                    task_db, activity.FACE_MATCH_COMPLETED, event_id=event_id, ip_address=ip,
                    detail={"matches": len(result)},
                )

            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        except Exception as e:
            logger.exception("Selfie processing failed for request_id=%s", request_id)
            _state_put(request_id, {
                "type": "error",
                "status": "error",
                "message": f"Processing failed: {str(e)}",
            })
        finally:
            task_db.close()

    # Start background processing
    asyncio.create_task(process_selfie_background())

    # Return immediately with request_id
    return {
        "request_id": request_id,
        "message": "Processing started. Connect to processing stream for updates.",
    }


@router.get("/{slug}/photos/{photo_id}/download", response_model=schemas.DownloadResponse)
@limiter.limit("30/minute")
def download_photo(
    slug: str,
    photo_id: int,
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    event = _get_event_or_404(slug, db)

    # Only photos the guest's selfie matched carry a valid token — photo ids
    # are sequential, so without this anyone with the slug could scrape the
    # whole gallery.
    if not signing.verify_download(token, event.id, photo_id):
        raise HTTPException(status_code=403, detail="Invalid or expired download token.")

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
    body: schemas.ZipRequest,
    db: Session = Depends(get_db),
):
    """Stream a ZIP of the requested photos (token-authorized, event-isolated)."""
    event = _get_event_or_404(slug, db)
    if not body.photos:
        raise HTTPException(status_code=400, detail="No photos selected.")

    # Every photo needs a valid match token (anti-scraping, same as single
    # download).
    verified_ids = [
        item.id for item in body.photos
        if signing.verify_download(item.token, event.id, item.id)
    ]
    if not verified_ids:
        raise HTTPException(status_code=403, detail="Invalid or expired download tokens.")

    # Only photos that belong to THIS event are included (isolation).
    photos = (
        db.query(models.Photo)
        .filter(models.Photo.id.in_(verified_ids), models.Photo.event_id == event.id)
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
