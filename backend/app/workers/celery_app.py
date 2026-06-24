"""Celery application factory.

Broker + result backend are Redis (settings.REDIS_URL). Tasks call existing
services; the web tier only enqueues. Task modules are added to `include` as
each is implemented (face_tasks in step B, thumb_tasks in D, maintenance in B).

Run a worker:
    celery -A app.workers.celery_app worker -Q face,thumbs,maintenance -c 4
Run beat (exactly one replica):
    celery -A app.workers.celery_app beat
"""
from datetime import timedelta

import time

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_prerun, task_postrun

from ..config import settings
from ..core.logging_config import configure_logging
from ..core.observability import init_sentry
from ..core.request_id import bind_request_id
from ..core.metrics import celery_tasks_total, celery_task_duration_seconds

celery_app = Celery(
    "wedfind",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.face_tasks",
        "app.workers.thumb_tasks",
        "app.workers.maintenance",
    ],
)

celery_app.conf.update(
    task_acks_late=True,                  # re-deliver if a worker dies mid-task
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,         # fair dispatch for long CPU tasks
    result_expires=3600,
    task_default_queue="default",
    task_routes={
        "app.workers.face_tasks.*": {"queue": "face"},
        "app.workers.thumb_tasks.*": {"queue": "thumbs"},
        "app.workers.maintenance.*": {"queue": "maintenance"},
    },
    task_time_limit=600,                  # hard 10 min ceiling per task
    task_soft_time_limit=540,
    beat_schedule={
        "retention-daily": {
            "task": "app.workers.maintenance.retention_sweep",
            "schedule": crontab(hour=3, minute=0),       # 03:00 UTC daily
        },
        "reset-stuck-15m": {
            "task": "app.workers.maintenance.reset_stuck_processing",
            "schedule": timedelta(minutes=15),
        },
    },
)


# Workers get the same JSON logging + Sentry as the web tier.
configure_logging()
init_sentry(celery=True)


_task_starts: dict[str, float] = {}


@task_prerun.connect
def _bind_request_id(task=None, task_id=None, **_):
    """Bind the propagated request id so worker logs correlate with the web request."""
    headers = getattr(getattr(task, "request", None), "headers", None) or {}
    bind_request_id(headers.get("request_id"))
    if task_id:
        _task_starts[task_id] = time.monotonic()


@task_postrun.connect
def _record_metrics(task=None, task_id=None, state=None, **_):
    name = getattr(task, "name", "unknown")
    celery_tasks_total.labels(name, (state or "unknown").lower()).inc()
    start = _task_starts.pop(task_id, None)
    if start is not None:
        celery_task_duration_seconds.labels(name).observe(time.monotonic() - start)


@celery_app.task(name="app.workers.ping")
def ping() -> str:
    """Liveness task for smoke-testing the broker/worker wiring."""
    return "pong"
