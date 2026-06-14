"""Admin endpoints: user management, audit log, analytics."""
from app.database import SessionLocal
from app.models import models
from app.services import activity, photo_ingest


def _create_event(client):
    return client.post(
        "/api/events/", json={"title": "Wedding", "event_date": "2026-09-01T00:00:00Z"}
    ).json()


# ---- user management ----

def test_list_users(client, as_studio):
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    assert any(u["role"] == "studio" for u in r.json())


def test_guest_blocked_from_admin(client, as_guest):
    assert client.get("/api/admin/users").status_code == 403


def test_change_user_role(client, as_studio):
    # make a second user to promote
    db = SessionLocal()
    try:
        u = models.User(firebase_uid="x2", email="g2@test.ai", name="g2", role="guest")
        db.add(u); db.commit(); db.refresh(u)
        uid = u.id
    finally:
        db.close()
    r = client.patch(f"/api/admin/users/{uid}/role", json={"role": "studio"})
    assert r.status_code == 200
    assert r.json()["role"] == "studio"


def test_cannot_demote_self(client, as_studio):
    me = client.get("/api/auth/me")  # current studio
    # find own id via users list
    users = client.get("/api/admin/users").json()
    my_id = [u["id"] for u in users if u["role"] == "studio"][0]
    r = client.patch(f"/api/admin/users/{my_id}/role", json={"role": "guest"})
    assert r.status_code == 400


# ---- audit log ----

def test_activity_scoped_to_owned_events(client, as_studio):
    ev = _create_event(client)
    db = SessionLocal()
    try:
        activity.log_activity(db, activity.EVENT_VIEWED, event_id=ev["id"], ip_address="1.1.1.1")
    finally:
        db.close()
    r = client.get("/api/admin/activity")
    assert r.status_code == 200
    assert any(a["action"] == "EVENT_VIEWED" for a in r.json())


# ---- analytics ----

def test_analytics_counts(client, as_studio):
    ev = _create_event(client)
    db = SessionLocal()
    try:
        photo_ingest.ingest_photo_bytes(db, ev["id"], "a.jpg", b"x" * 50, "image/jpeg")
        activity.log_activity(db, activity.EVENT_VIEWED, event_id=ev["id"], ip_address="1.1.1.1")
        activity.log_activity(db, activity.FACE_MATCH_COMPLETED, event_id=ev["id"], ip_address="1.1.1.1")
        db.add(models.GuestConsent(event_id=ev["id"], ip_address="1.1.1.1", consent_version="1.0"))
        db.commit()
    finally:
        db.close()
    r = client.get("/api/admin/analytics")
    assert r.status_code == 200
    body = r.json()
    assert body["total_events"] >= 1
    assert body["total_photos"] >= 1
    assert body["total_scans"] >= 1
    assert body["total_matches"] >= 1
    assert body["total_consents"] >= 1
    ev_row = [e for e in body["per_event"] if e["event_id"] == ev["id"]][0]
    assert ev_row["photos"] == 1
    assert ev_row["scans"] == 1
    assert ev_row["matches"] == 1
