"""Celery wiring smoke tests (eager mode — no broker needed)."""
from app.workers.celery_app import celery_app, ping


def test_ping_eager():
    celery_app.conf.task_always_eager = True
    try:
        assert ping.delay().get() == "pong"
    finally:
        celery_app.conf.task_always_eager = False


def test_queue_routes_configured():
    routes = celery_app.conf.task_routes
    assert routes["app.workers.face_tasks.*"]["queue"] == "face"
    assert routes["app.workers.thumb_tasks.*"]["queue"] == "thumbs"
    assert routes["app.workers.maintenance.*"]["queue"] == "maintenance"


def test_reliability_flags():
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
