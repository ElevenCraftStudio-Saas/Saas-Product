"""Correlation id middleware + logging config + sentry no-op."""
from app.core.logging_config import configure_logging
from app.core.observability import init_sentry


def test_request_id_generated_and_echoed(client):
    r = client.get("/livez")
    assert r.headers.get("X-Request-ID")


def test_request_id_passthrough(client):
    r = client.get("/livez", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


def test_configure_logging_idempotent():
    configure_logging()
    configure_logging()  # must not raise


def test_init_sentry_noop_without_dsn():
    init_sentry()       # SENTRY_DSN unset in tests → no-op, no raise
    init_sentry(celery=True)
