"""Face-processing migration: dispatch flag + idempotent reprocess."""
import numpy as np

from app.config import settings
from app.database import SessionLocal
from app.models import models
from app.services import dispatch, face_processing
from tests.conftest import make_user


class _FakeFace:
    embedding = np.array([0.1] * 512, dtype=float)
    bbox = np.array([0.0, 0.0, 1.0, 1.0])


def _seed_local_photo():
    owner = make_user(role="user", email="f@test.ai", firebase_uid="f-uid")
    db = SessionLocal()
    try:
        e = models.Event(title="E", event_slug="f-1", photographer_id=owner.id)
        db.add(e); db.commit(); db.refresh(e)
        p = models.Photo(event_id=e.id, filename="a.jpg", filepath="a.jpg",
                         storage_provider="local", storage_key=None)
        db.add(p); db.commit(); db.refresh(p)
        return p.id
    finally:
        db.close()


def test_dispatch_uses_celery_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "USE_CELERY", True)
    calls = {}
    import app.workers.face_tasks as ft
    monkeypatch.setattr(ft.process_photo, "apply_async",
                        lambda args=None, headers=None: calls.setdefault("id", args[0]))
    dispatch.enqueue_process_photo(123)
    assert calls["id"] == 123


def test_dispatch_uses_background_tasks_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "USE_CELERY", False)
    added = {}

    class BG:
        def add_task(self, fn, *a):
            added["args"] = a

    dispatch.enqueue_process_photo(7, BG())
    assert added["args"] == (7,)


def test_process_photo_idempotent(monkeypatch):
    monkeypatch.setattr(face_processing.face_engine, "get_faces", lambda p: [_FakeFace()])
    pid = _seed_local_photo()

    face_processing.process_photo_faces(pid)
    face_processing.process_photo_faces(pid)  # re-run must not duplicate

    db = SessionLocal()
    try:
        n = db.query(models.FaceEmbedding).filter(models.FaceEmbedding.photo_id == pid).count()
        status = db.query(models.Photo).get(pid).processing_status
    finally:
        db.close()
    assert n == 1
    assert status == models.ProcessingStatus.COMPLETED
