from app.routers import deps
from app.database import SessionLocal
from app.models import models


def test_first_user_is_studio_rest_are_guests():
    db = SessionLocal()
    try:
        u1 = deps._find_or_create_user({"uid": "a", "email": "first@test.ai"}, db)
        u2 = deps._find_or_create_user({"uid": "b", "email": "second@test.ai"}, db)
        assert u1.role == "studio"
        assert u2.role == "guest"
    finally:
        db.close()


def test_me_returns_current_user(client, as_studio):
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["role"] == "studio"


def test_studio_can_promote(client, as_studio):
    # target guest must exist first
    db = SessionLocal()
    try:
        db.add(models.User(firebase_uid="t", email="target@test.ai", name="t", role="guest"))
        db.commit()
    finally:
        db.close()
    r = client.post("/api/auth/promote", json={"email": "target@test.ai", "role": "studio"})
    assert r.status_code == 200
    assert r.json()["role"] == "studio"


def test_guest_cannot_promote(client, as_guest):
    r = client.post("/api/auth/promote", json={"email": "x@test.ai", "role": "studio"})
    assert r.status_code == 403
