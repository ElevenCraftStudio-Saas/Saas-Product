"""Folder monitoring via watchdog.

IMPORTANT: watchdog observes the **backend host's** filesystem. This works
when the backend runs on the studio's machine (local/desktop-agent model).
In a cloud deployment the backend cannot see the studio's D:\ drive — that
requires a separate desktop agent (see production notes).

Responsibilities:
- Start/stop an Observer per enabled FolderWatch.
- On new image file: dedup, ingest via the shared pipeline, trigger embeddings.
- Initial scan on start (catches files added while the backend was down).
"""
import os
import time
import threading
import logging
from datetime import datetime, timezone

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ..database import SessionLocal
from ..models import models
from .photo_ingest import ingest_photo_bytes, photo_exists, is_allowed_image
from .face_processing import process_photo_faces

logger = logging.getLogger("wedfind.watcher")


class _ImageHandler(FileSystemEventHandler):
    def __init__(self, manager: "WatcherManager", event_id: int):
        self._manager = manager
        self._event_id = event_id

    def on_created(self, event):
        if not event.is_directory:
            self._manager.handle_file(self._event_id, event.src_path)

    def on_moved(self, event):
        # e.g. editors that write temp then rename into place
        if not event.is_directory:
            self._manager.handle_file(self._event_id, event.dest_path)


class WatcherManager:
    def __init__(self):
        self._observers: dict[int, Observer] = {}   # watch_id -> Observer
        self._lock = threading.Lock()

    # ---- core ingest of one file (called from watchdog thread or scan) ----
    def handle_file(self, event_id: int, path: str) -> bool:
        if not is_allowed_image(path):
            return False
        if not self._wait_until_stable(path):
            return False
        filename = os.path.basename(path)
        db = SessionLocal()
        photo_id = None
        try:
            if photo_exists(db, event_id, filename):
                logger.info("WATCH_SKIP_DUP event=%s file=%s", event_id, filename)
                return False
            with open(path, "rb") as f:
                content = f.read()
            photo = ingest_photo_bytes(db, event_id, filename, content)
            photo_id = photo.id
            logger.info("WATCH_UPLOAD event=%s file=%s photo_id=%s", event_id, filename, photo_id)
        except FileNotFoundError:
            return False
        except Exception:
            logger.exception("WATCH_INGEST_FAILED event=%s path=%s", event_id, path)
            return False
        finally:
            db.close()

        # Trigger embeddings off the watcher thread (opens its own session).
        threading.Thread(target=process_photo_faces, args=(photo_id,), daemon=True).start()
        return True

    @staticmethod
    def _wait_until_stable(path: str, tries: int = 6, delay: float = 0.4) -> bool:
        """Wait for a file to finish being written (size stops changing)."""
        last = -1
        for _ in range(tries):
            try:
                size = os.path.getsize(path)
            except OSError:
                return False
            if size > 0 and size == last:
                return True
            last = size
            time.sleep(delay)
        return last > 0

    # ---- scan whole folder (initial + manual rescan) ----
    def scan(self, watch_id: int, event_id: int, folder: str) -> int:
        uploaded = 0
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                p = os.path.join(folder, name)
                if os.path.isfile(p) and is_allowed_image(name):
                    if self.handle_file(event_id, p):
                        uploaded += 1
        db = SessionLocal()
        try:
            w = db.get(models.FolderWatch, watch_id)
            if w:
                w.last_scan_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()
        logger.info("WATCH_SCAN event=%s folder=%s uploaded=%s", event_id, folder, uploaded)
        return uploaded

    # ---- lifecycle ----
    def is_watching(self, watch_id: int) -> bool:
        return watch_id in self._observers

    def start(self, watch: models.FolderWatch) -> None:
        with self._lock:
            if watch.id in self._observers:
                return
            if not os.path.isdir(watch.folder_path):
                logger.warning("WATCH_START_SKIP folder missing: %s", watch.folder_path)
                return
            observer = Observer()
            observer.schedule(_ImageHandler(self, watch.event_id), watch.folder_path, recursive=False)
            observer.daemon = True
            observer.start()
            self._observers[watch.id] = observer
            logger.info("WATCH_START id=%s event=%s folder=%s", watch.id, watch.event_id, watch.folder_path)
        # Initial scan outside the lock — catches files added while offline.
        self.scan(watch.id, watch.event_id, watch.folder_path)

    def stop(self, watch_id: int) -> None:
        with self._lock:
            observer = self._observers.pop(watch_id, None)
        if observer:
            observer.stop()
            observer.join(timeout=3)
            logger.info("WATCH_STOP id=%s", watch_id)

    def start_all(self) -> None:
        db = SessionLocal()
        try:
            watches = db.query(models.FolderWatch).filter(models.FolderWatch.enabled.is_(True)).all()
        finally:
            db.close()
        for w in watches:
            try:
                self.start(w)
            except Exception:
                logger.exception("WATCH_START_ALL failed for id=%s", w.id)
        logger.info("WATCH_START_ALL started=%s", len(self._observers))

    def stop_all(self) -> None:
        for wid in list(self._observers.keys()):
            self.stop(wid)


watcher_manager = WatcherManager()
