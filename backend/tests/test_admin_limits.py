"""Admin quota management: users payload, event-limit, storage-limit, role."""
from tests.conftest import make_user
from app.database import SessionLocal
from app.models import models


def _seed_user_events(email, uid, n):
    u = make_user(role="user", email=email, firebase_uid=uid)
    db = SessionLocal()
    try:
        for i in range(n):
            db.add(models.Event(title=f"E{i}", event_slug=f"{uid}-{i}", photographer_id=u.id))
        db.commit()
    finally:
        db.close()
    return u


def test_users_payload(client, as_admin):
    s = _seed_user_events("s1@test.ai", "s1", 1)
    r = client.get("/api/admin/users")
    assert r.status_code == 200
    row = next(x for x in r.json() if x["id"] == s.id)
    assert row["event_count"] == 1
    assert row["effective_limit"] == 2
    assert row["effective_storage_limit_mb"] == 2048
    assert row["storage_used_mb"] == 0
    assert row["max_events"] is None


def test_set_limit(client, as_admin):
    s = _seed_user_events("s2@test.ai", "s2", 0)
    r = client.patch(f"/api/admin/users/{s.id}/limit", json={"max_events": 7})
    assert r.status_code == 200
    assert r.json()["effective_limit"] == 7


def test_set_limit_rejects_negative(client, as_admin):
    s = _seed_user_events("s2b@test.ai", "s2b", 0)
    assert client.patch(f"/api/admin/users/{s.id}/limit", json={"max_events": -1}).status_code == 400


def test_set_storage(client, as_admin):
    s = _seed_user_events("s3@test.ai", "s3", 0)
    r = client.patch(f"/api/admin/users/{s.id}/storage", json={"storage_limit_mb": 500})
    assert r.status_code == 200
    assert r.json()["effective_storage_limit_mb"] == 500


def test_quota_endpoints_reject_user(client, as_user):
    assert client.get("/api/admin/users").status_code == 403


def test_role_change_pending_to_user(client, as_admin):
    s = _seed_user_events("s4@test.ai", "s4", 0)
    db = SessionLocal()
    try:
        db.query(models.User).filter(models.User.id == s.id).update({"role": "pending"})
        db.commit()
    finally:
        db.close()
    r = client.patch(f"/api/admin/users/{s.id}/role", json={"role": "user"})
    assert r.status_code == 200
    assert r.json()["role"] == "user"
