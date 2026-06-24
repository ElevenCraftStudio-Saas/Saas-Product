"""ADMIN_EMAILS allowlist: provisioning + login upgrade."""
from app.config import settings
from app.database import SessionLocal
from app.routers import deps
from tests.conftest import make_user


def test_allowlisted_new_user_is_admin(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "boss@x.com")
    db = SessionLocal()
    try:
        admin = deps._find_or_create_user({"uid": "boss", "email": "Boss@X.com"}, db)
        regular = deps._find_or_create_user({"uid": "reg", "email": "reg@x.com"}, db)
        assert admin.role == "admin"
        assert regular.role == "user"
    finally:
        db.close()


def test_allowlisted_existing_user_upgraded_on_login(monkeypatch):
    make_user(role="user", email="late@x.com", firebase_uid="late")
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "late@x.com")
    db = SessionLocal()
    try:
        u = deps._find_or_create_user({"uid": "late", "email": "late@x.com"}, db)
        assert u.role == "admin"
    finally:
        db.close()


def test_non_allowlisted_not_demoted(monkeypatch):
    # An existing admin not in the allowlist stays admin (never auto-demoted here).
    make_user(role="admin", email="keep@x.com", firebase_uid="keep")
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "")
    db = SessionLocal()
    try:
        u = deps._find_or_create_user({"uid": "keep", "email": "keep@x.com"}, db)
        assert u.role == "admin"
    finally:
        db.close()
