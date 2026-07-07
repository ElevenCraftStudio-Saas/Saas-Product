"""Guest-flow security hardening tests.

Covers:
- download authorization via HMAC match tokens (no gallery scraping)
- request_id must be a UUID (client cannot choose guessable SSE keys)
- SSE state TTL eviction + terminal-state cleanup (no unbounded growth)
- SSE stream ends promptly on error states (no 60s hangs)
- X-Forwarded-For is not trusted for consent/erasure identity
"""
import io
import time
import uuid

import pytest

from app.core import signing
from app.database import SessionLocal
from app.models import models
from app.routers import guest as guest_router


def _png_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 40)).save(buf, "PNG")
    return buf.getvalue()


def _uuid():
    return str(uuid.uuid4())


def _create_event(client):
    return client.post(
        "/api/events/", json={"title": "Wedding", "event_date": "2026-09-01T00:00:00Z"}
    ).json()


def _add_photo(event_id: int, filename: str = "p1.jpg") -> int:
    db = SessionLocal()
    try:
        p = models.Photo(
            event_id=event_id,
            filename=filename,
            filepath=f"uploads/{filename}",
            storage_provider="s3",
            storage_key=f"events/{event_id}/{filename}",
            processing_status=models.ProcessingStatus.COMPLETED,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p.id
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Isolate rate-limit state between tests."""
    guest_router.limiter.reset()
    yield
    guest_router.limiter.reset()


# ---------------------------------------------------------------- tokens


def test_download_without_token_rejected(client, as_studio):
    ev = _create_event(client)
    pid = _add_photo(ev["id"])
    client.app.dependency_overrides.clear()

    r = client.get(f"/api/guest/{ev['event_slug']}/photos/{pid}/download")
    assert r.status_code in (401, 403, 422)


def test_download_with_forged_token_rejected(client, as_studio):
    ev = _create_event(client)
    pid = _add_photo(ev["id"])
    client.app.dependency_overrides.clear()

    r = client.get(
        f"/api/guest/{ev['event_slug']}/photos/{pid}/download",
        params={"token": "deadbeef.badsig"},
    )
    assert r.status_code == 403


def test_download_with_valid_token_succeeds(client, as_studio):
    ev = _create_event(client)
    pid = _add_photo(ev["id"])
    client.app.dependency_overrides.clear()

    token = signing.sign_download(ev["id"], pid)
    r = client.get(
        f"/api/guest/{ev['event_slug']}/photos/{pid}/download",
        params={"token": token},
    )
    assert r.status_code == 200
    assert r.json()["url"]


def test_download_token_bound_to_photo(client, as_studio):
    ev = _create_event(client)
    pid_a = _add_photo(ev["id"], "a.jpg")
    pid_b = _add_photo(ev["id"], "b.jpg")
    client.app.dependency_overrides.clear()

    token_a = signing.sign_download(ev["id"], pid_a)
    r = client.get(
        f"/api/guest/{ev['event_slug']}/photos/{pid_b}/download",
        params={"token": token_a},
    )
    assert r.status_code == 403


def test_download_token_expires():
    token = signing.sign_download(1, 2, ttl=-1)  # already expired
    assert not signing.verify_download(token, 1, 2)


def test_zip_requires_valid_tokens(client, as_studio):
    ev = _create_event(client)
    pid = _add_photo(ev["id"])
    client.app.dependency_overrides.clear()

    # Forged token → nothing downloadable → 403
    r = client.post(
        f"/api/guest/{ev['event_slug']}/download-zip",
        json={"photos": [{"id": pid, "token": "deadbeef.badsig"}]},
    )
    assert r.status_code == 403

    # Valid token → zip streams
    token = signing.sign_download(ev["id"], pid)
    r = client.post(
        f"/api/guest/{ev['event_slug']}/download-zip",
        json={"photos": [{"id": pid, "token": token}]},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"


def test_selfie_match_payload_carries_working_tokens(client, as_studio, monkeypatch):
    """Completed SSE payload must include download_token per photo, and the
    token must actually authorize the download endpoint."""
    ev = _create_event(client)
    pid = _add_photo(ev["id"])
    client.app.dependency_overrides.clear()

    class _Face:
        embedding = [0.1] * 512

    monkeypatch.setattr(guest_router.face_engine, "get_faces", lambda p: [_Face()])
    monkeypatch.setattr(guest_router, "match_event", lambda *a, **k: [pid])

    rid = _uuid()
    r = client.post(
        f"/api/guest/{ev['event_slug']}/selfie",
        files={"file": ("s.png", _png_bytes(), "image/png")},
        data={"consent": "true", "request_id": rid},
    )
    assert r.status_code == 200

    stream = client.get(
        f"/api/guest/{ev['event_slug']}/processing-stream", params={"request_id": rid}
    )
    assert "download_token" in stream.text

    import json as json_mod
    completed = None
    for line in stream.text.splitlines():
        if line.startswith("data: "):
            frame = json_mod.loads(line[len("data: "):])
            if frame.get("status") == "completed":
                completed = frame
    assert completed and completed["photos"], stream.text
    token = completed["photos"][0]["download_token"]
    assert token

    r = client.get(
        f"/api/guest/{ev['event_slug']}/photos/{pid}/download",
        params={"token": token},
    )
    assert r.status_code == 200


# ---------------------------------------------------------------- request_id

def test_selfie_rejects_non_uuid_request_id(client, as_studio):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()

    r = client.post(
        f"/api/guest/{ev['event_slug']}/selfie",
        files={"file": ("s.png", _png_bytes(), "image/png")},
        data={"consent": "true", "request_id": "guessable-123"},
    )
    assert r.status_code in (400, 422)


# ---------------------------------------------------------------- SSE state

def test_state_helpers_roundtrip():
    """Guest router delegates to the processing-state store (TTL eviction is
    covered in test_processing_state.py)."""
    rid = _uuid()
    guest_router._state_put(rid, {"type": "progress", "status": "starting"})
    assert guest_router._state_get(rid) == {"type": "progress", "status": "starting"}
    guest_router._state_pop(rid)
    assert guest_router._state_get(rid) is None


def test_stream_ends_fast_and_pops_error_state(client, as_studio):
    """Error states must terminate the stream promptly (no 60s poll loop) and
    be removed once delivered."""
    ev = _create_event(client)
    client.app.dependency_overrides.clear()

    rid = _uuid()
    r = client.post(
        f"/api/guest/{ev['event_slug']}/selfie",
        files={"file": ("s.png", _png_bytes(), "image/png")},
        data={"consent": "false", "request_id": rid},
    )
    assert r.status_code == 200

    start = time.monotonic()
    stream = client.get(
        f"/api/guest/{ev['event_slug']}/processing-stream", params={"request_id": rid}
    )
    elapsed = time.monotonic() - start
    assert stream.status_code == 200
    assert "consent" in stream.text.lower()
    assert elapsed < 10, f"stream took {elapsed:.1f}s — terminal state must end it"
    assert guest_router._state_get(rid) is None


def test_stream_unknown_request_id_ends_fast(client, as_studio):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()

    start = time.monotonic()
    stream = client.get(
        f"/api/guest/{ev['event_slug']}/processing-stream",
        params={"request_id": _uuid()},
    )
    elapsed = time.monotonic() - start
    assert stream.status_code == 200
    assert elapsed < 15, f"stream took {elapsed:.1f}s for unknown request_id"


# ---------------------------------------------------------------- client IP

def test_xff_header_not_trusted_for_consent_identity(client, as_studio):
    ev = _create_event(client)
    client.app.dependency_overrides.clear()

    rid = _uuid()
    r = client.post(
        f"/api/guest/{ev['event_slug']}/selfie",
        files={"file": ("s.png", _png_bytes(), "image/png")},
        data={"consent": "true", "request_id": rid},
        headers={"X-Forwarded-For": "6.6.6.6"},
    )
    assert r.status_code == 200
    # Drain the stream so the background task finishes before we assert.
    client.get(
        f"/api/guest/{ev['event_slug']}/processing-stream", params={"request_id": rid}
    )

    db = SessionLocal()
    try:
        consents = (
            db.query(models.GuestConsent)
            .filter(models.GuestConsent.event_id == ev["id"])
            .all()
        )
        assert consents, "consent should have been recorded"
        assert all(c.ip_address != "6.6.6.6" for c in consents), (
            "spoofed X-Forwarded-For must not become the consent identity"
        )
    finally:
        db.close()
