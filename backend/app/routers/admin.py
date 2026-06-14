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
from .deps import get_current_studio

router = APIRouter()


# ---------------------- User management ----------------------

@router.get("/users", response_model=List[schemas.UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_studio),
):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@router.patch("/users/{user_id}/role", response_model=schemas.UserResponse)
def set_user_role(
    user_id: int,
    body: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_studio),
):
    if body.role not in ("studio", "guest"):
        raise HTTPException(status_code=400, detail="role must be 'studio' or 'guest'")
    if user_id == admin.id and body.role != "studio":
        raise HTTPException(status_code=400, detail="You cannot demote yourself")
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = body.role
    db.commit()
    db.refresh(target)
    return target


# ---------------------- Audit log viewer ----------------------

@router.get("/activity", response_model=List[schemas.ActivityRecord])
def list_activity(
    event_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio),
):
    # Only events owned by this studio.
    owned_ids = [
        eid for (eid,) in db.query(models.Event.id)
        .filter(models.Event.photographer_id == current_user.id).all()
    ]
    if not owned_ids:
        return []
    q = db.query(models.ActivityLog).filter(models.ActivityLog.event_id.in_(owned_ids))
    if event_id is not None:
        if event_id not in owned_ids:
            raise HTTPException(status_code=404, detail="Event not found")
        q = q.filter(models.ActivityLog.event_id == event_id)
    if action:
        q = q.filter(models.ActivityLog.action == action)
    limit = max(1, min(limit, 500))
    return q.order_by(models.ActivityLog.created_at.desc()).limit(limit).all()


# ---------------------- Analytics ----------------------

@router.get("/analytics", response_model=schemas.AnalyticsSummary)
def analytics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_studio),
):
    events = (
        db.query(models.Event)
        .filter(models.Event.photographer_id == current_user.id)
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
