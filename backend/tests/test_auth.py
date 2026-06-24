from app.routers import deps
from app.database import SessionLocal
from app.models import models


def test_new_users_are_user():
    db = SessionLocal()
    try:
        u1 = deps._find_or_create_user({"uid": "a", "email": "first@test.ai"}, db)
        u2 = deps._find_or_create_user({"uid": "b", "email": "second@test.ai"}, db)
        assert u1.role == "user"
        assert u2.role == "user"
    finally:
        db.close()


def test_me_returns_current_user(client, as_user):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["role"] == "user"


def test_admin_can_promote(client, as_admin):
    # target user must exist first; promote to admin
    db = SessionLocal()
    try:
        db.add(models.User(firebase_uid="t", email="target@test.ai", name="t", role="user"))
        db.commit()
    finally:
        db.close()
    r = client.post("/api/auth/promote", json={"email": "target@test.ai", "role": "admin"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_user_cannot_promote(client, as_user):
    r = client.post("/api/auth/promote", json={"email": "x@test.ai", "role": "user"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Admin access required"
