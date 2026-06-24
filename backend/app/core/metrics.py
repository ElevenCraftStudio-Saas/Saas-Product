"""Domain Prometheus metrics (incremented from services / signals).

HTTP metrics come from prometheus-fastapi-instrumentator; these are the
business counters. Importing this module is cheap and side-effect-free beyond
registering the collectors on the default registry.
"""
from prometheus_client import Counter, Histogram

photos_processed_total = Counter(
    "wedfind_photos_processed_total", "Photos face-processed", ["result"]  # completed|failed
)
faces_detected_total = Counter(
    "wedfind_faces_detected_total", "Faces detected across processed photos"
)
thumbnails_total = Counter(
    "wedfind_thumbnails_total", "Thumbnails generated", ["result"]  # ok|fail
)
selfie_matches_total = Counter(
    "wedfind_selfie_matches_total", "Guest selfie match attempts", ["matched"]  # yes|no
)
quota_rejections_total = Counter(
    "wedfind_quota_rejections_total", "Quota rejections", ["kind"]  # event|storage
)
celery_tasks_total = Counter(
    "wedfind_celery_tasks_total", "Celery task outcomes", ["task", "state"]  # success|failure|retry
)
celery_task_duration_seconds = Histogram(
    "wedfind_celery_task_duration_seconds", "Celery task duration", ["task"]
)
