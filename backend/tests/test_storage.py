"""Storage quota enforcement + Photo.size_bytes accounting at ingest."""
import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app.models import models
from app.services import photo_ingest
from tests.conftest import make_user


def _event_for(owner):
    db = SessionLocal()
    try:
        e = models.Event(title="E", event_slug=f"slug-{owner.id}", photographer_id=owner.id)
        db.add(e)
        db.commit()
        db.refresh(e)
        return e.id
    finally:
        db.close()


def test_ingest_records_size_bytes():
    owner = make_user(role="user", email="st1@test.ai", firebase_uid="st1")
    eid = _event_for(owner)
    db = SessionLocal()
    try:
        photo = photo_ingest.ingest_photo_bytes(db, eid, "a.jpg", b"X" * 1234, "image/jpeg")
        assert photo.size_bytes == 1234
    finally:
        db.close()


def test_ingest_blocks_over_storage_limit():
    owner = make_user(role="user", email="st2@test.ai", firebase_uid="st2")
    db = SessionLocal()
    try:
        db.query(models.User).filter(models.User.id == owner.id).update({"storage_limit_mb": 0})
        db.commit()
    finally:
        db.close()
    eid = _event_for(owner)
    db = SessionLocal()
    try:
        with pytest.raises(HTTPException) as e:
            photo_ingest.ingest_photo_bytes(db, eid, "a.jpg", b"X" * 10, "image/jpeg")
        assert e.value.status_code == 403
        assert e.value.detail == "Storage limit reached. Contact your admin to raise it."
    finally:
        db.close()
