"""Admin endpoints: user management, audit log, analytics (admin-only, global)."""
from app.database import SessionLocal
from app.models import models
from app.services import activity, photo_ingest
from tests.conftest import make_user


def _create_event(client):
    return client.post(
        "/api/events/", json={"title": "Wedding", "event_date": "2026-09-01T00:00:00Z"}
    ).json()


def _other_users_event_with_activity():
    """Seed an event owned by a DIFFERENT user (not the admin) + one activity row."""
    owner = make_user(role="user", email="other@test.ai", firebase_uid="other-uid")
    db = SessionLocal()
    try:
        e = models.Event(title="OtherWedding", event_slug="other-1", photographer_id=owner.id)
        db.add(e); db.commit(); db.refresh(e)
        activity.log_activity(db, activity.EVENT_VIEWED, event_id=e.id, ip_address="2.2.2.2")
        return e.id
    finally:
        db.close()


# ---- user management ----

def test_list_users(client, as_admin):
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    assert any(u["role"] == "admin" for u in r.json())


def test_user_blocked_from_admin(client, as_user):
    assert client.get("/api/admin/users").status_code == 403


def test_promote_user_to_admin(client, as_admin):
    db = SessionLocal()
    try:
        u = models.User(firebase_uid="x2", email="u2@test.ai", name="u2", role="user")
        db.add(u); db.commit(); db.refresh(u)
        uid = u.id
    finally:
        db.close()
    r = client.patch(f"/api/admin/users/{uid}/role", json={"role": "admin"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_role_must_be_user_or_admin(client, as_admin):
    db = SessionLocal()
    try:
        u = models.User(firebase_uid="x3", email="u3@test.ai", name="u3", role="user")
        db.add(u); db.commit(); db.refresh(u)
        uid = u.id
    finally:
        db.close()
    assert client.patch(f"/api/admin/users/{uid}/role", json={"role": "pending"}).status_code == 400


def test_cannot_demote_last_admin(client, as_admin):
    users = client.get("/api/admin/users").json()
    admin_id = [u["id"] for u in users if u["role"] == "admin"][0]
    r = client.patch(f"/api/admin/users/{admin_id}/role", json={"role": "user"})
    assert r.status_code == 400  # last-admin lock


def test_can_demote_admin_when_another_exists(client, as_admin):
    # Seed a second admin, then the first can be demoted.
    db = SessionLocal()
    try:
        db.add(models.User(firebase_uid="a2", email="a2@test.ai", name="a2", role="admin"))
        db.commit()
    finally:
        db.close()
    users = client.get("/api/admin/users").json()
    a2_id = [u["id"] for u in users if u["email"] == "a2@test.ai"][0]
    r = client.patch(f"/api/admin/users/{a2_id}/role", json={"role": "user"})
    assert r.status_code == 200
    assert r.json()["role"] == "user"


# ---- audit log (global) ----

def test_activity_global(client, as_admin):
    ev = _create_event(client)
    db = SessionLocal()
    try:
        activity.log_activity(db, activity.EVENT_VIEWED, event_id=ev["id"], ip_address="1.1.1.1")
    finally:
        db.close()
    r = client.get("/api/admin/activity")
    assert r.status_code == 200
    assert any(a["action"] == "EVENT_VIEWED" for a in r.json())


def test_activity_includes_other_users_events(client, as_admin):
    eid = _other_users_event_with_activity()
    r = client.get("/api/admin/activity")
    assert r.status_code == 200
    assert any(a["event_id"] == eid for a in r.json())  # admin sees events it doesn't own


def test_analytics_includes_other_users_events(client, as_admin):
    eid = _other_users_event_with_activity()
    r = client.get("/api/admin/analytics")
    assert r.status_code == 200
    assert any(e["event_id"] == eid for e in r.json()["per_event"])


# ---- analytics (global) ----

def test_analytics_counts(client, as_admin):
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
