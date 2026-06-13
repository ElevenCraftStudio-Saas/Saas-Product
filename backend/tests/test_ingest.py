import pytest
from app.database import SessionLocal
from app.models import models
from app.services import photo_ingest


def _make_event(db):
    ev = models.Event(title="E", event_slug="e-1", storage_provider="s3", storage_key="qr/e.png")
    db.add(ev); db.commit(); db.refresh(ev)
    return ev


def test_ingest_creates_photo_and_dedups():
    db = SessionLocal()
    try:
        ev = _make_event(db)
        assert photo_ingest.photo_exists(db, ev.id, "a.jpg") is False
        p = photo_ingest.ingest_photo_bytes(db, ev.id, "a.jpg", b"x" * 100, "image/jpeg")
        assert p.id and p.storage_provider == "s3"
        assert photo_ingest.photo_exists(db, ev.id, "a.jpg") is True
    finally:
        db.close()


def test_ingest_rejects_bad_type():
    db = SessionLocal()
    try:
        ev = _make_event(db)
        with pytest.raises(ValueError):
            photo_ingest.ingest_photo_bytes(db, ev.id, "a.gif", b"x" * 10, "image/gif")
    finally:
        db.close()


def test_is_allowed_image():
    assert photo_ingest.is_allowed_image("p.JPG")
    assert photo_ingest.is_allowed_image("p.webp")
    assert not photo_ingest.is_allowed_image("p.txt")
