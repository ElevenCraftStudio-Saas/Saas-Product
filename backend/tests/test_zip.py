import io
import zipfile
from app.core import signing
from app.database import SessionLocal
from app.models import models
from app.services import photo_ingest


def _create_event(client):
    return client.post("/api/events/", json={"title": "Wedding", "event_date": "2026-09-01T00:00:00Z"}).json()


def test_download_zip(client, as_studio):
    ev = _create_event(client)
    # add two photos to the event
    db = SessionLocal()
    try:
        p1 = photo_ingest.ingest_photo_bytes(db, ev["id"], "a.jpg", b"x" * 50, "image/jpeg")
        p2 = photo_ingest.ingest_photo_bytes(db, ev["id"], "b.jpg", b"y" * 50, "image/jpeg")
        ids = [p1.id, p2.id]
    finally:
        db.close()

    client.app.dependency_overrides.clear()  # zip endpoint is public (token-authorized)
    items = [{"id": pid, "token": signing.sign_download(ev["id"], pid)} for pid in ids]
    r = client.post(f"/api/guest/{ev['event_slug']}/download-zip", json={"photos": items})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert len(zf.namelist()) == 2


def test_download_zip_event_isolation(client, as_studio):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()
    # Token minted for ANOTHER event's id must not authorize photos here, and
    # a photo id from no event → not found / forbidden.
    item = {"id": 999999, "token": signing.sign_download(ev["id"] + 1, 999999)}
    r = client.post(f"/api/guest/{ev['event_slug']}/download-zip", json={"photos": [item]})
    assert r.status_code == 403

    # Even with a validly-signed token for this event, a photo that doesn't
    # exist in the event is 404.
    item = {"id": 999999, "token": signing.sign_download(ev["id"], 999999)}
    r = client.post(f"/api/guest/{ev['event_slug']}/download-zip", json={"photos": [item]})
    assert r.status_code == 404
