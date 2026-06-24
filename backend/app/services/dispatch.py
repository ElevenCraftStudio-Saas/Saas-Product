"""Indirection for triggering async photo work.

Respects the USE_CELERY flag so the system can roll back to the in-process
path (FastAPI BackgroundTasks for the web upload, daemon thread for the folder
watcher) without code changes.
"""
import threading

from ..config import settings
from .face_processing import process_photo_faces


def enqueue_process_photo(photo_id: int, background_tasks=None) -> None:
    if settings.USE_CELERY:
        from ..workers.face_tasks import process_photo
        process_photo.delay(photo_id)
    elif background_tasks is not None:
        background_tasks.add_task(process_photo_faces, photo_id)
    else:
        threading.Thread(target=process_photo_faces, args=(photo_id,), daemon=True).start()
