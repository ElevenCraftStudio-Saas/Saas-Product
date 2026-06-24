"""/metrics endpoint + domain counters."""
from app.core import metrics


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_request" in r.text or "wedfind_" in r.text


def test_photos_processed_counter_increments(monkeypatch):
    import numpy as np
    from app.database import SessionLocal
    from app.models import models
    from app.services import face_processing
    from tests.conftest import make_user

    class _F:
        embedding = np.array([0.1] * 512, dtype=float)
        bbox = np.array([0.0, 0.0, 1.0, 1.0])

    monkeypatch.setattr(face_processing.face_engine, "get_faces", lambda p: [_F()])
    owner = make_user(role="user", email="mx@test.ai", firebase_uid="mx")
    db = SessionLocal()
    try:
        e = models.Event(title="E", event_slug="mx-1", photographer_id=owner.id)
        db.add(e); db.commit(); db.refresh(e)
        p = models.Photo(event_id=e.id, filename="a.jpg", filepath="a.jpg", storage_provider="local")
        db.add(p); db.commit(); db.refresh(p)
        pid = p.id
    finally:
        db.close()

    before = metrics.photos_processed_total.labels("completed")._value.get()
    face_processing.process_photo_faces(pid)
    after = metrics.photos_processed_total.labels("completed")._value.get()
    assert after == before + 1
