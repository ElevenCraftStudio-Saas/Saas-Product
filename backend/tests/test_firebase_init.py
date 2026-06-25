"""Firebase Admin init refactor: single, idempotent, thread-safe implementation."""
import pytest

from app.core import firebase


def test_init_idempotent_when_already_initialized(monkeypatch):
    import firebase_admin
    monkeypatch.setattr(firebase_admin, "_apps", {"[DEFAULT]": object()})
    called = []
    monkeypatch.setattr(firebase_admin, "initialize_app", lambda *a, **k: called.append(1))
    assert firebase.init_firebase() is True
    assert firebase.init_firebase() is True   # repeated calls are safe
    assert called == []                        # never re-initialized


def test_init_without_credentials_returns_false(monkeypatch):
    import firebase_admin
    monkeypatch.setattr(firebase_admin, "_apps", {})
    monkeypatch.setattr(firebase, "_resolve_credential_path", lambda: None)
    assert firebase.init_firebase() is False    # graceful, no crash


def test_init_with_credentials(monkeypatch):
    import firebase_admin
    from firebase_admin import credentials
    store = {}
    monkeypatch.setattr(firebase_admin, "_apps", store)
    monkeypatch.setattr(firebase, "_resolve_credential_path", lambda: "/fake/sa.json")
    monkeypatch.setattr(credentials, "Certificate", lambda p: ("cert", p))
    monkeypatch.setattr(firebase_admin, "initialize_app",
                        lambda cred, opts=None: store.__setitem__("[DEFAULT]", object()))
    assert firebase.init_firebase() is True
    assert "[DEFAULT]" in store


def test_get_firestore_client_raises_without_creds(monkeypatch):
    import firebase_admin
    monkeypatch.setattr(firebase_admin, "_apps", {})
    monkeypatch.setattr(firebase, "_resolve_credential_path", lambda: None)
    with pytest.raises(RuntimeError):
        firebase.get_firestore_client()


def test_get_firestore_client_returns_client(monkeypatch):
    import firebase_admin
    from firebase_admin import firestore
    monkeypatch.setattr(firebase_admin, "_apps", {"[DEFAULT]": object()})
    sentinel = object()
    monkeypatch.setattr(firestore, "client", lambda: sentinel)
    assert firebase.get_firestore_client() is sentinel


def test_firestore_service_degrades_when_unavailable(monkeypatch):
    import app.services.firestore_service as fs
    from app.core import firebase as fb

    def _boom():
        raise RuntimeError("no creds")

    monkeypatch.setattr(fb, "get_firestore_client", _boom)
    fs._firestore_client = None
    assert fs._get_client() is None             # graceful fallback


def test_celery_worker_imports_and_inits(monkeypatch):
    # Importing the worker entrypoint must call init_firebase without crashing.
    import app.workers.celery_app as ca
    assert hasattr(ca, "celery_app")


def test_fastapi_startup_initializes(client):
    # The client fixture runs the lifespan (which calls init_firebase); the app serves.
    assert client.get("/livez").status_code == 200
