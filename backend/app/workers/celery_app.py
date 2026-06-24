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

from celery import Celery
from celery.schedules import crontab

from ..config import settings

celery_app = Celery(
    "wedfind",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.workers.face_tasks",
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


@celery_app.task(name="app.workers.ping")
def ping() -> str:
    """Liveness task for smoke-testing the broker/worker wiring."""
    return "pong"
