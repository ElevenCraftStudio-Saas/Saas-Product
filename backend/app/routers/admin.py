"""Admin endpoints (studio-gated).

- User management: list users, change role (reuses the studio role gate as admin).
- Audit log viewer: recent ActivityLog rows for the studio's own events.
- Analytics: per-event scans / matches / downloads / consents / photos.

Activity + analytics are scoped to events the current studio owns; user
management is global (the bootstrap studio acts as the system admin).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import models
from ..schemas import schemas
from ..services import activity
from .deps import require_admin
from ..core.limits import (
    effective_event_limit, effective_storage_limit_mb, user_storage_used_bytes,
)

router = APIRouter()


def _admin_user(db: Session, u: models.User) -> schemas.AdminUserResponse:
    ec = db.query(models.Event.id).filter(models.Event.photographer_id == u.id).count()
    used_mb = user_storage_used_bytes(db, u) // (1024 * 1024)
    return schemas.AdminUserResponse(
        id=u.id, firebase_uid=u.firebase_uid, name=u.name, email=u.email, phone=u.phone,
        role=u.role, max_events=u.max_events, storage_limit_mb=u.storage_limit_mb,
        created_at=u.created_at, event_count=ec,
        effective_limit=effective_event_limit(u),
        effective_storage_limit_mb=effective_storage_limit_mb(u),
        storage_used_mb=used_mb,
    )


# ---------------------- User management ----------------------

@router.get("/users", response_model=List[schemas.AdminUserResponse])
def list_users(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return [_admin_user(db, u) for u in users]


@router.patch("/users/{user_id}/role", response_model=schemas.AdminUserResponse)
def set_user_role(
    user_id: int,
    body: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    if body.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="role must be 'user' or 'admin'")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    # Last-admin lock: never let the only admin be demoted (lockout protection).
    if target.role == "admin" and body.role != "admin":
        admin_count = db.query(models.User).filter(models.User.role == "admin").count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last admin")
    target.role = body.role
    db.commit()
    db.refresh(target)
    return _admin_user(db, target)


@router.patch("/users/{user_id}/limit", response_model=schemas.AdminUserResponse)
def set_user_limit(
    user_id: int,
    body: schemas.EventLimitUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    if body.max_events is not None and body.max_events < 0:
        raise HTTPException(status_code=400, detail="max_events must be null or >= 0")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.max_events = body.max_events
    db.commit()
    db.refresh(target)
    return _admin_user(db, target)


@router.patch("/users/{user_id}/storage", response_model=schemas.AdminUserResponse)
def set_user_storage(
    user_id: int,
    body: schemas.StorageLimitUpdate,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    if body.storage_limit_mb is not None and body.storage_limit_mb < 0:
        raise HTTPException(status_code=400, detail="storage_limit_mb must be null or >= 0")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.storage_limit_mb = body.storage_limit_mb
    db.commit()
    db.refresh(target)
    return _admin_user(db, target)


# ---------------------- Audit log viewer ----------------------

@router.get("/activity", response_model=List[schemas.ActivityRecord])
def list_activity(
    event_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    # Admin sees all activity globally.
    q = db.query(models.ActivityLog)
    if event_id is not None:
        q = q.filter(models.ActivityLog.event_id == event_id)
    if action:
        q = q.filter(models.ActivityLog.action == action)
    limit = max(1, min(limit, 500))
    return q.order_by(models.ActivityLog.created_at.desc()).limit(limit).all()


# ---------------------- Analytics ----------------------

@router.get("/analytics", response_model=schemas.AnalyticsSummary)
def analytics(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    events = (
        db.query(models.Event)
        .order_by(models.Event.created_at.desc())
        .all()
    )
    event_ids = [e.id for e in events]

    def _counts(model_action_col, ids):
        if not ids:
            return {}
        rows = (
            db.query(model_action_col, func.count())
            .filter(model_action_col.in_(ids))
            .group_by(model_action_col)
            .all()
        )
        return {k: v for k, v in rows}

    photos_by_event = _counts(models.Photo.event_id, event_ids)
    consents_by_event = _counts(models.GuestConsent.event_id, event_ids)

    # Activity counts grouped by (event_id, action).
    act_map = {}
    if event_ids:
        rows = (
            db.query(models.ActivityLog.event_id, models.ActivityLog.action, func.count())
            .filter(models.ActivityLog.event_id.in_(event_ids))
            .group_by(models.ActivityLog.event_id, models.ActivityLog.action)
            .all()
        )
        for eid, action_name, cnt in rows:
            act_map.setdefault(eid, {})[action_name] = cnt

    per_event = []
    t_photos = t_consents = t_scans = t_matches = t_downloads = 0
    for e in events:
        a = act_map.get(e.id, {})
        photos = photos_by_event.get(e.id, 0)
        consents = consents_by_event.get(e.id, 0)
        scans = a.get(activity.EVENT_VIEWED, 0)
        matches = a.get(activity.FACE_MATCH_COMPLETED, 0)
        downloads = a.get(activity.PHOTO_DOWNLOADED, 0)
        per_event.append(schemas.EventAnalytics(
            event_id=e.id, title=e.title, photos=photos, consents=consents,
            scans=scans, matches=matches, downloads=downloads,
        ))
        t_photos += photos; t_consents += consents
        t_scans += scans; t_matches += matches; t_downloads += downloads

    return schemas.AnalyticsSummary(
        total_events=len(events), total_photos=t_photos, total_consents=t_consents,
        total_scans=t_scans, total_matches=t_matches, total_downloads=t_downloads,
        per_event=per_event,
    )
