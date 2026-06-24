"""Failure-path + cascade coverage."""
import datetime

from app.database import SessionLocal
from app.models import models
from app.services import face_processing, thumbnails
from app.services.s3_service import s3_service
from app.workers import maintenance
from tests.conftest import make_user


def _seed_s3_photo(status=models.ProcessingStatus.PENDING, uploaded_at=None):
    owner = make_user(role="user", email="r@test.ai", firebase_uid="r-uid")
    db = SessionLocal()
    try:
        e = models.Event(title="E", event_slug="r-1", photographer_id=owner.id)
        db.add(e); db.commit(); db.refresh(e)
        p = models.Photo(event_id=e.id, filename="a.jpg", filepath="a.jpg",
                         storage_provider="s3", storage_key="events/1/a.jpg",
                         processing_status=status)
        db.add(p); db.commit(); db.refresh(p)
        if uploaded_at is not None:
            db.query(models.Photo).filter(models.Photo.id == p.id).update({"uploaded_at": uploaded_at})
            db.commit()
        return e.id, p.id
    finally:
        db.close()


def test_process_photo_s3_download_failure(monkeypatch):
    monkeypatch.setattr(s3_service, "download_to_temp", lambda key, path: False)
    _, pid = _seed_s3_photo()
    face_processing.process_photo_faces(pid)  # swallows, marks FAILED
    db = SessionLocal()
    try:
        assert db.query(models.Photo).get(pid).processing_status == models.ProcessingStatus.FAILED
    finally:
        db.close()


def test_thumbnail_failure_when_no_bytes(monkeypatch):
    monkeypatch.setattr(thumbnails.s3_service, "get_bytes", lambda key: None)
    _, pid = _seed_s3_photo()
    assert thumbnails.make_thumbnail_for_photo(pid) is False


def test_reset_stuck_processing(monkeypatch):
    old = datetime.datetime(2020, 1, 1)
    _, pid = _seed_s3_photo(status=models.ProcessingStatus.PROCESSING, uploaded_at=old)
    enqueued = []
    import app.workers.face_tasks as ft
    monkeypatch.setattr(ft.process_photo, "delay", lambda p: enqueued.append(p))

    res = maintenance.reset_stuck_processing()
    assert res["reset"] >= 1
    assert pid in enqueued
    db = SessionLocal()
    try:
        assert db.query(models.Photo).get(pid).processing_status == models.ProcessingStatus.PENDING
    finally:
        db.close()


def test_backfill_thumbnails_enqueues_missing(monkeypatch):
    _, pid = _seed_s3_photo()  # thumb_key is NULL
    enqueued = []
    import app.workers.thumb_tasks as tt
    monkeypatch.setattr(tt.make_thumbnail, "delay", lambda p: enqueued.append(p))
    res = tt.backfill_thumbnails()
    assert res["enqueued"] >= 1
    assert pid in enqueued


def test_retention_sweep_task_runs():
    res = maintenance.retention_sweep()
    assert "photos" in res  # purge_expired returns a summary dict


def test_event_delete_cascades_photos_orm():
    owner = make_user(role="user", email="c@test.ai", firebase_uid="c-uid")
    db = SessionLocal()
    try:
        e = models.Event(title="E", event_slug="c-1", photographer_id=owner.id)
        db.add(e); db.commit(); db.refresh(e)
        p = models.Photo(event_id=e.id, filename="a.jpg", filepath="a.jpg")
        db.add(p); db.commit(); db.refresh(p)
        db.add(models.FaceEmbedding(photo_id=p.id, event_id=e.id, embedding=[0.1]))
        db.commit()
        eid, pid = e.id, p.id

        ev = db.query(models.Event).get(eid)
        db.delete(ev)  # ORM cascade removes photos + embeddings
        db.commit()

        assert db.query(models.Photo).filter(models.Photo.event_id == eid).count() == 0
        assert db.query(models.FaceEmbedding).filter(models.FaceEmbedding.photo_id == pid).count() == 0
    finally:
        db.close()
