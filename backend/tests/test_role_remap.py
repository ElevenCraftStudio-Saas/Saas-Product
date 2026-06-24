"""Proves the migration's role remap migrates existing data safely:
lowest-id -> admin, old studio -> user, old guest -> pending, exactly one admin.
"""
from app.database import SessionLocal
from app.models import models
from app.core.role_migration import remap_roles


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


def test_remap_assigns_roles_deterministically():
    first = _seed("studio", "owner@test.ai", "owner")   # lowest id -> admin
    studio2 = _seed("studio", "s2@test.ai", "s2")        # -> user
    guest1 = _seed("guest", "g1@test.ai", "g1")          # -> pending

    db = SessionLocal()
    try:
        remap_roles(db.connection())
        db.commit()
        roles = {u.id: u.role for u in db.query(models.User).all()}
    finally:
        db.close()

    assert roles[first] == "admin"
    assert roles[studio2] == "user"
    assert roles[guest1] == "pending"
    assert list(roles.values()).count("admin") == 1


def test_remap_idempotent():
    _seed("studio", "a@test.ai", "a")
    db = SessionLocal()
    try:
        remap_roles(db.connection())
        db.commit()
        remap_roles(db.connection())  # second run must not change anything
        db.commit()
        roles = [u.role for u in db.query(models.User).all()]
    finally:
        db.close()
    assert roles.count("admin") == 1
