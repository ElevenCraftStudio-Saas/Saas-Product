"""Thumbnail generation + dispatch + backfill."""
import io

from PIL import Image

from app.config import settings
from app.database import SessionLocal
from app.models import models
from app.services import thumbnails, dispatch
from tests.conftest import make_user


def _png_bytes(w=1000, h=800):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 30, 60)).save(buf, format="PNG")
    return buf.getvalue()


def _seed_photo():
    owner = make_user(role="user", email="t@test.ai", firebase_uid="t-uid")
    db = SessionLocal()
    try:
        e = models.Event(title="E", event_slug="t-1", photographer_id=owner.id)
        db.add(e); db.commit(); db.refresh(e)
        p = models.Photo(event_id=e.id, filename="a.jpg", filepath="a.jpg",
                         storage_provider="s3", storage_key="events/1/a.jpg")
        db.add(p); db.commit(); db.refresh(p)
        return p.id
    finally:
        db.close()


def test_make_thumbnail_sets_key(monkeypatch):
    # conftest mocks get_bytes to fixed bytes; supply a real PNG instead.
    monkeypatch.setattr(thumbnails.s3_service, "get_bytes", lambda key: _png_bytes())
    uploaded = {}
    monkeypatch.setattr(thumbnails.s3_service, "upload_file",
                        lambda buf, key, ct: uploaded.update(key=key, ct=ct) or True)
    pid = _seed_photo()

    ok = thumbnails.make_thumbnail_for_photo(pid)
    assert ok is True
    assert uploaded["ct"] == "image/webp"
    assert "/thumbs/" in uploaded["key"]

    db = SessionLocal()
    try:
        assert db.query(models.Photo).get(pid).thumb_key == uploaded["key"]
    finally:
        db.close()


def test_thumbnail_dispatch_celery(monkeypatch):
    monkeypatch.setattr(settings, "USE_CELERY", True)
    calls = {}
    import app.workers.thumb_tasks as tt
    monkeypatch.setattr(tt.make_thumbnail, "delay", lambda pid: calls.setdefault("id", pid))
    dispatch.enqueue_make_thumbnail(42)
    assert calls["id"] == 42
