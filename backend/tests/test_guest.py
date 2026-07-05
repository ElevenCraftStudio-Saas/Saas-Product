import io
import uuid
from app.core import signing
from app.routers import guest as guest_router


class _Face:
    def __init__(self, emb):
        self.embedding = emb


def _png_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 40)).save(buf, "PNG")
    return buf.getvalue()


def _uuid():
    return str(uuid.uuid4())


def _create_event(client):
    return client.post("/api/events/", json={"title": "Wedding", "event_date": "2026-09-01T00:00:00Z"}).json()


def test_public_event_view(client, as_studio):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()  # guest view is public
    r = client.get(f"/api/guest/{ev['event_slug']}")
    assert r.status_code == 200
    assert r.json()["event_slug"] == ev["event_slug"]


def test_selfie_requires_consent(client, as_studio):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()
    rid = _uuid()
    r = client.post(
        f"/api/guest/{ev['event_slug']}/selfie",
        files={"file": ("s.png", _png_bytes(), "image/png")},
        data={"consent": "false", "request_id": rid},
    )
    # Endpoint returns 200 immediately, validation surfaces via SSE
    assert r.status_code == 200
    stream_r = client.get(f"/api/guest/{ev['event_slug']}/processing-stream?request_id={rid}")
    assert stream_r.status_code == 200
    assert "consent" in stream_r.text.lower()


def test_selfie_no_face(client, as_studio, monkeypatch):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()
    monkeypatch.setattr(guest_router.face_engine, "get_faces", lambda p: [])
    rid = _uuid()
    r = client.post(
        f"/api/guest/{ev['event_slug']}/selfie",
        files={"file": ("s.png", _png_bytes(), "image/png")},
        data={"consent": "true", "request_id": rid},
    )
    assert r.status_code == 200
    # Stream ends on the terminal error state (no polling loop needed).
    stream_r = client.get(f"/api/guest/{ev['event_slug']}/processing-stream?request_id={rid}")
    assert stream_r.status_code == 200
    assert "no face" in stream_r.text.lower()


def test_selfie_multi_face(client, as_studio, monkeypatch):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()
    monkeypatch.setattr(guest_router.face_engine, "get_faces", lambda p: [_Face([0.1]), _Face([0.2])])
    rid = _uuid()
    r = client.post(
        f"/api/guest/{ev['event_slug']}/selfie",
        files={"file": ("s.png", _png_bytes(), "image/png")},
        data={"consent": "true", "request_id": rid},
    )
    assert r.status_code == 200
    stream_r = client.get(f"/api/guest/{ev['event_slug']}/processing-stream?request_id={rid}")
    assert stream_r.status_code == 200
    assert "multiple" in stream_r.text.lower()


def test_download_event_isolation(client, as_studio):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()
    # Even with a validly-signed token, a photo that isn't in this event is 404.
    token = signing.sign_download(ev["id"], 999999)
    r = client.get(
        f"/api/guest/{ev['event_slug']}/photos/999999/download",
        params={"token": token},
    )
    assert r.status_code == 404
