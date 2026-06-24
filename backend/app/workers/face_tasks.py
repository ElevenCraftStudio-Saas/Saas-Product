"""Face-embedding Celery tasks (queue: face)."""
import logging

from .celery_app import celery_app
from ..services.face_processing import process_photo_faces

logger = logging.getLogger("wedfind.face")


@celery_app.task(
    name="app.workers.face_tasks.process_photo",
    bind=True,
    acks_late=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def process_photo(self, photo_id: int):
    """Detect + embed faces for a photo. Retries transient failures with
    exponential backoff; the photo is marked FAILED on the final attempt
    (process_photo_faces sets it before re-raising)."""
    process_photo_faces(photo_id, raise_on_error=True)
