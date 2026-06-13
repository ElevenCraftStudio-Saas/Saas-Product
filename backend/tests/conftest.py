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


def make_user(role="studio", email="u@test.ai", firebase_uid="uid-1"):
    db = _db_session()
    try:
        u = models.User(firebase_uid=firebase_uid, email=email, name=email, role=role)
        db.add(u)
        db.commit()
        db.refresh(u)
        return u
    finally:
        db.close()


@pytest.fixture
def as_studio():
    """Override auth deps to act as a studio user; returns the user."""
    user = make_user(role="studio", email="studio@test.ai", firebase_uid="studio-uid")

    def _current():
        db = _db_session()
        try:
            return db.query(models.User).filter(models.User.id == user.id).first()
        finally:
            db.close()

    app_main.app.dependency_overrides[deps.get_current_user] = _current
    app_main.app.dependency_overrides[deps.get_current_studio] = _current
    return user


@pytest.fixture
def as_guest():
    """Override auth: authenticated guest (studio-gated routes must 403)."""
    user = make_user(role="guest", email="guest@test.ai", firebase_uid="guest-uid")

    def _current():
        db = _db_session()
        try:
            return db.query(models.User).filter(models.User.id == user.id).first()
        finally:
            db.close()

    # get_current_user returns the guest; get_current_studio must still enforce role.
    app_main.app.dependency_overrides[deps.get_current_user] = _current
    return user
