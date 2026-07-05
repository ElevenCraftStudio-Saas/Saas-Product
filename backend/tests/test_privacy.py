"""DPDP privacy layer: retention sweep, consent ledger/export, erasure."""
import csv
import io
import datetime

from app.database import SessionLocal
from app.models import models
from app.services import photo_ingest, retention


def _create_event(client):
    return client.post(
        "/api/events/", json={"title": "Wedding", "event_date": "2026-09-01T00:00:00Z"}
    ).json()


def _add_consent(event_id, ip="1.2.3.4"):
    db = SessionLocal()
    try:
        db.add(models.GuestConsent(
            event_id=event_id, ip_address=ip, consent_version="1.0",
            consent_text="I consent", user_agent="pytest",
        ))
        db.commit()
    finally:
        db.close()


# ---- retention summary + update ----

def test_retention_default_off(client, as_admin):
    ev = _create_event(client)
    r = client.get(f"/api/events/{ev['id']}/privacy")
    assert r.status_code == 200
    body = r.json()
    assert body["retention_days"] is None
    assert body["scheduled_purge_at"] is None


def test_set_retention_computes_purge_date(client, as_admin):
    ev = _create_event(client)
    r = client.patch(f"/api/events/{ev['id']}/retention", json={"retention_days": 30})
    assert r.status_code == 200
    assert r.json()["retention_days"] == 30
    assert r.json()["scheduled_purge_at"] is not None  # event_date + 30d


def test_retention_rejects_zero(client, as_admin):
    ev = _create_event(client)
    r = client.patch(f"/api/events/{ev['id']}/retention", json={"retention_days": 0})
    assert r.status_code == 400


# ---- consent ledger + export ----

def test_consent_ledger_and_csv_export(client, as_admin):
    ev = _create_event(client)
    _add_consent(ev["id"])
    _add_consent(ev["id"], ip="5.6.7.8")

    r = client.get(f"/api/events/{ev['id']}/consents")
    assert r.status_code == 200
    assert len(r.json()) == 2

    r2 = client.get(f"/api/events/{ev['id']}/consents/export?format=csv")
    assert r2.status_code == 200
    assert r2.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r2.content.decode())))
    assert rows[0][0] == "id"          # header
    assert len(rows) == 3              # header + 2 records


# ---- retention sweep ----

def test_purge_expired_deletes_old_event_photos(client, as_admin):
    ev = _create_event(client)
    db = SessionLocal()
    try:
        # backdate the event well past a 1-day retention window
        event = db.query(models.Event).filter(models.Event.id == ev["id"]).first()
        event.event_date = datetime.datetime(2020, 1, 1)
        event.retention_days = 1
        db.commit()
        photo_ingest.ingest_photo_bytes(db, ev["id"], "a.jpg", b"x" * 50, "image/jpeg")

        result = retention.purge_expired(db)
        assert result["events"] == 1
        assert result["photos"] == 1
        remaining = db.query(models.Photo).filter(models.Photo.event_id == ev["id"]).count()
        assert remaining == 0
    finally:
        db.close()


def test_purge_skips_non_expired(client, as_admin):
    ev = _create_event(client)
    db = SessionLocal()
    try:
        event = db.query(models.Event).filter(models.Event.id == ev["id"]).first()
        event.event_date = datetime.datetime(2099, 1, 1)  # future
        event.retention_days = 1
        db.commit()
        photo_ingest.ingest_photo_bytes(db, ev["id"], "a.jpg", b"x" * 50, "image/jpeg")

        result = retention.purge_expired(db)
        assert result["photos"] == 0
        assert db.query(models.Photo).filter(models.Photo.event_id == ev["id"]).count() == 1
    finally:
        db.close()


# ---- erasure ----

def test_erase_removes_only_caller_ip(client, as_admin):
    ev = _create_event(client)
    _add_consent(ev["id"], ip="testclient")  # the caller's real (socket) IP
    _add_consent(ev["id"], ip="8.8.8.8")     # someone else's record

    client.app.dependency_overrides.clear()  # erase is public
    # A spoofed X-Forwarded-For must NOT redirect erasure onto another IP —
    # identity comes from the socket/proxy-resolved client, not headers.
    r = client.post(f"/api/guest/{ev['event_slug']}/erase", headers={"x-forwarded-for": "8.8.8.8"})
    assert r.status_code == 200
    assert r.json()["consents_deleted"] == 1

    db = SessionLocal()
    try:
        remaining = db.query(models.GuestConsent).filter(
            models.GuestConsent.event_id == ev["id"]
        ).all()
        assert len(remaining) == 1
        assert remaining[0].ip_address == "8.8.8.8"  # untouched despite the header
    finally:
        db.close()
