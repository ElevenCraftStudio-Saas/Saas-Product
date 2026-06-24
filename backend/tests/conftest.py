"""Test fixtures.

Forces a local SQLite DB (set BEFORE importing the app so app.database binds
to it), mocks S3 + the face engine, and provides auth-override helpers.
"""
import os
os.environ["DATABASE_URL"] = "sqlite:///./test_wedfind.db"  # before app import

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, get_db
from app import main as app_main
from app.routers import deps
from app.models import models
from app.services import s3_service as s3_module
from app.services import photo_ingest


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _mock_s3(monkeypatch):
    """No real S3 in tests."""
    monkeypatch.setattr(s3_module.s3_service, "upload_file", lambda *a, **k: True)
    monkeypatch.setattr(s3_module.s3_service, "delete_file", lambda *a, **k: True)
    monkeypatch.setattr(
        s3_module.s3_service, "generate_presigned_url", lambda *a, **k: "https://signed.example/x"
    )
    monkeypatch.setattr(s3_module.s3_service, "get_bytes", lambda *a, **k: b"FAKEIMAGEBYTES")


@pytest.fixture
def client():
    app = app_main.app
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _db_session():
    from app.database import SessionLocal
    return SessionLocal()


def make_user(role="user", email="u@test.ai", firebase_uid="uid-1"):
    db = _db_session()
    try:
        u = models.User(firebase_uid=firebase_uid, email=email, name=email, role=role)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u
    finally:
        db.close()


def _override_current(user):
    def _current():
        db = _db_session()
        try:
            return db.query(models.User).filter(models.User.id == user.id).first()
        finally:
            db.close()
    return _current


@pytest.fixture
def as_admin():
    """Act as the admin; overrides admin + user gates (admin tests may hit user routes)."""
    user = make_user(role="admin", email="admin@test.ai", firebase_uid="admin-uid")
    cur = _override_current(user)
    app_main.app.dependency_overrides[deps.get_current_user] = cur
    app_main.app.dependency_overrides[deps.require_admin] = cur
    app_main.app.dependency_overrides[deps.require_user] = cur
    return user


@pytest.fixture
def as_user():
    """Act as a studio user."""
    user = make_user(role="user", email="user@test.ai", firebase_uid="user-uid")
    cur = _override_current(user)
    app_main.app.dependency_overrides[deps.get_current_user] = cur
    app_main.app.dependency_overrides[deps.require_user] = cur
    return user


@pytest.fixture
def as_pending():
    """Act as a pending (no-access) user; role gates must still 403."""
    user = make_user(role="pending", email="pending@test.ai", firebase_uid="pending-uid")
    cur = _override_current(user)
    app_main.app.dependency_overrides[deps.get_current_user] = cur
    return user


# Back-compat aliases so not-yet-migrated tests keep importing; map to new roles.
@pytest.fixture
def as_studio(as_user):
    return as_user


@pytest.fixture
def as_guest(as_pending):
    return as_pending
