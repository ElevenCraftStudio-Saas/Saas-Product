import pytest
from fastapi import HTTPException
from app.database import SessionLocal
from app.routers import deps
from tests.conftest import make_user


def test_new_user_is_pending():
    db = SessionLocal()
    try:
        u = deps._find_or_create_user({"uid": "x1", "email": "x1@test.ai"}, db)
        assert u.role == "pending"
    finally:
        db.close()


def test_no_auto_admin_even_for_first_user():
    db = SessionLocal()
    try:
        first = deps._find_or_create_user({"uid": "f1", "email": "f1@test.ai"}, db)
        assert first.role == "pending"
    finally:
        db.close()


def test_require_admin_allows_admin():
    a = make_user(role="admin", email="a@test.ai", firebase_uid="a-uid")
    assert deps.require_admin(a) is a


def test_require_admin_rejects_user():
    u = make_user(role="user", email="u@test.ai", firebase_uid="u-uid")
    with pytest.raises(HTTPException) as e:
        deps.require_admin(u)
    assert e.value.status_code == 403
    assert e.value.detail == "Admin access required"


def test_require_user_rejects_pending():
    p = make_user(role="pending", email="p@test.ai", firebase_uid="p-uid")
    with pytest.raises(HTTPException) as e:
        deps.require_user(p)
    assert e.value.status_code == 403
    assert e.value.detail == "Studio access required"
