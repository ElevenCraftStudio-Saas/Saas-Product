"""Migration f6a7b8c9d0e1 removes the 'pending' role: pending -> user,
admins untouched, idempotent."""
from app.database import SessionLocal
from app.models import models
from app.core.role_migration import collapse_pending


def _seed(role, email, uid):
    db = SessionLocal()
    try:
        u = models.User(firebase_uid=uid, email=email, name=email, role=role)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def test_collapse_pending_to_user():
    a = _seed("admin", "a@test.ai", "a")
    u = _seed("user", "u@test.ai", "u")
    p = _seed("pending", "p@test.ai", "p")

    db = SessionLocal()
    try:
        collapse_pending(db.connection())
        db.commit()
        roles = {x.id: x.role for x in db.query(models.User).all()}
    finally:
        db.close()

    assert roles[a] == "admin"   # admin untouched
    assert roles[u] == "user"
    assert roles[p] == "user"    # pending collapsed
    assert "pending" not in roles.values()


def test_collapse_pending_idempotent():
    _seed("pending", "p2@test.ai", "p2")
    db = SessionLocal()
    try:
        collapse_pending(db.connection())
        db.commit()
        collapse_pending(db.connection())
        db.commit()
        roles = [x.role for x in db.query(models.User).all()]
    finally:
        db.close()
    assert "pending" not in roles
