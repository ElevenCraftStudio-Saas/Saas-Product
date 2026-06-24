"""/livez always up; /readyz 503 when any dependency is degraded."""
from app import main as m


def test_livez(client):
    r = client.get("/livez")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_readyz_ok(client, monkeypatch):
    monkeypatch.setattr(m, "_check_db", lambda db: True)
    monkeypatch.setattr(m, "_check_redis", lambda: True)
    monkeypatch.setattr(m, "_check_s3", lambda: True)
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok", "redis": "ok", "s3": "ok"}


def test_readyz_degraded_returns_503(client, monkeypatch):
    monkeypatch.setattr(m, "_check_db", lambda db: True)
    monkeypatch.setattr(m, "_check_redis", lambda: False)
    monkeypatch.setattr(m, "_check_s3", lambda: True)
    r = client.get("/readyz")
    assert r.status_code == 503
    assert r.json()["redis"] == "error"


def test_security_headers_present(client):
    r = client.get("/livez")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" in r.headers
    assert "Content-Security-Policy" in r.headers
