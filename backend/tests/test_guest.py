import io
import time
from app.routers import guest as guest_router


class _Face:
    def __init__(self, emb):
        self.embedding = emb


def _png_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 40)).save(buf, "PNG")
    return buf.getvalue()


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
    r = client.post(
        f"/api/guest/{ev['event_slug']}/selfie",
        files={"file": ("s.png", _png_bytes(), "image/png")},
        data={"consent": "false", "request_id": "test-123"},
    )
    # Endpoint returns 200 immediately, validation happens async via SSE
    assert r.status_code == 200
    # Poll processing stream to check for consent error
    stream_r = client.get(f"/api/guest/{ev['event_slug']}/processing-stream?request_id=test-123")
    assert stream_r.status_code == 200
    # Stream should contain error about consent
    stream_data = stream_r.text
    assert "Consent is required" in stream_data or "consent" in stream_data.lower()
    assert "consent" in r.json()["detail"].lower()


def test_selfie_no_face(client, as_studio, monkeypatch):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()
    monkeypatch.setattr(guest_router.face_engine, "get_faces", lambda p: [])
    r = client.post(
        f"/api/guest/{ev['event_slug']}/selfie",
        files={"file": ("s.png", _png_bytes(), "image/png")},
        data={"consent": "true", "request_id": "test-no-face"},
    )
    # Endpoint returns 200 immediately, validation happens async via SSE
    assert r.status_code == 200
    # Poll processing stream to check for no face error
    for _ in range(10):  # Poll for up to 1 second
        stream_r = client.get(f"/api/guest/{ev['event_slug']}/processing-stream?request_id=test-no-face")
        if stream_r.status_code == 200:
            stream_data = stream_r.text
            if "no face" in stream_data.lower() or "error" in stream_data.lower():
                return
        time.sleep(0.1)
    assert False, "No face error not found in stream"
    assert "no face" in r.json()["detail"].lower()


def test_selfie_multi_face(client, as_studio, monkeypatch):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()
    monkeypatch.setattr(guest_router.face_engine, "get_faces", lambda p: [_Face([0.1]), _Face([0.2])])
    r = client.post(
        f"/api/guest/{ev['event_slug']}/selfie",
        files={"file": ("s.png", _png_bytes(), "image/png")},
        data={"consent": "true", "request_id": "test-multi-face"},
    )
    # Endpoint returns 200 immediately, validation happens async via SSE
    assert r.status_code == 200
    # Poll processing stream to check for multiple faces error
    for _ in range(10):  # Poll for up to 1 second
        stream_r = client.get(f"/api/guest/{ev['event_slug']}/processing-stream?request_id=test-multi-face")
        if stream_r.status_code == 200:
            stream_data = stream_r.text
            if "multiple" in stream_data.lower() or "error" in stream_data.lower():
                return
        time.sleep(0.1)
    assert False, "Multiple faces error not found in stream"
    assert "multiple" in r.json()["detail"].lower()


def test_download_event_isolation(client, as_studio):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()
    r = client.get(f"/api/guest/{ev['event_slug']}/photos/999999/download")
    assert r.status_code == 404
