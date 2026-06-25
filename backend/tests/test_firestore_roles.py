"""Tests for Firestore-backed role management.

Replaces previous ADMIN_EMAILS allowlist tests. Roles come from Firestore,
not environment variables.
"""
from fastapi.testclient import TestClient
from app.models import models
from app.routers import deps
from tests.conftest import _db_session


def _get_user_by_email(email: str) -> models.User | None:
    db = _db_session()
    try:
        return db.query(models.User).filter(models.User.email == email).first()
    finally:
        db.close()


def test_new_user_defaults_to_user_role(client: TestClient, monkeypatch):
    """A new Firebase user with no matching Firestore 'admin' email gets 'user'."""
    import app.services.firestore_service as fs
    monkeypatch.setattr(fs, "ensure_user_doc", lambda uid, email, name: "user")

    decoded = {"uid": "new-uid", "email": "new@test.ai", "name": "New"}
    db = _db_session()
    try:
        user = deps._find_or_create_user(decoded, db)
        assert user.role == "user"
        assert user.email == "new@test.ai"
    finally:
        db.close()


def test_admin_role_granted_via_firestore(client: TestClient, monkeypatch):
    """A new Firebase user marked 'admin' in Firestore gets admin role."""
    import app.services.firestore_service as fs
    monkeypatch.setattr(fs, "ensure_user_doc", lambda uid, email, name: "admin")

    decoded = {"uid": "admin-uid", "email": "admin@test.ai", "name": "Admin"}
    db = _db_session()
    try:
        user = deps._find_or_create_user(decoded, db)
        assert user.role == "admin"
    finally:
        db.close()


def test_firestore_role_synced_on_login(client: TestClient, monkeypatch):
    """When Firestore role differs from PostgreSQL, DB role is updated on login."""
    import app.services.firestore_service as fs
    # First login: user role.
    monkeypatch.setattr(fs, "ensure_user_doc", lambda uid, email, name: "user")
    decoded = {"uid": "sync-uid", "email": "sync@test.ai", "name": "Sync"}
    db = _db_session()
    try:
        user = deps._find_or_create_user(decoded, db)
        assert user.role == "user"
    finally:
        db.close()

    # Second login: Firestore now says admin.
    monkeypatch.setattr(fs, "ensure_user_doc", lambda uid, email, name: "admin")
    db2 = _db_session()
    try:
        user = deps._find_or_create_user(decoded, db2)
        assert user.role == "admin"
    finally:
        db2.close()


def test_admin_promote_syncs_firestore(client: TestClient, as_admin, monkeypatch):
    """The /promote endpoint calls Firestore set_user_role after DB update."""
    import app.services.firestore_service as fs
    calls = []
    monkeypatch.setattr(fs, "set_user_role", lambda uid, role, email="", display_name="": calls.append((uid, role)))

    # Create the target user first.
    db = _db_session()
    try:
        u = models.User(firebase_uid="target-uid", email="target@test.ai", name="Target", role="user")
        db.add(u)
        db.commit()
        db.refresh(u)
        target_id = u.id
    finally:
        db.close()

        resp = client.post("/api/auth/promote", json={"email": "target@test.ai", "role": "admin"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
    assert len(calls) == 1
    assert calls[0] == ("target-uid", "admin")


def test_admin_promote_last_admin_protection(client: TestClient, as_admin):
    """Cannot demote the only remaining admin."""
    # as_admin creates one admin. Try to demote them via the promote endpoint
    # by their email.
    resp = client.post("/api/auth/promote", json={"email": "admin@test.ai", "role": "user"})
    assert resp.status_code == 400
    assert "last admin" in resp.text.lower()


def test_admin_promote_user_not_found(client: TestClient, as_admin):
    """Promoting a non-existent email returns 404."""
    resp = client.post("/api/auth/promote", json={"email": "nobody@test.ai", "role": "admin"})
    assert resp.status_code == 404
