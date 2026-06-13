"""WedFind desktop ingest agent.

Watches a local folder and pushes new photos to the WedFind backend using a
studio API key (X-API-Key). Survives restarts (local state file), retries on
failure, and skips already-synced files.

Usage:
    python wedfind_agent.py --config config.json
    python wedfind_agent.py --api-url https://api.example.com/api \
        --api-key wfa_xxx --event-id 12 --folder "D:/Wedding/Event12"

Config file (JSON) keys: api_url, api_key, event_id, folder, [poll_seconds].
"""
import argparse
import hashlib
import json
import logging
import os
import queue
import sys
import threading
import time

import requests
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("wedfind-agent")

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
STABLE_CHECKS = 3        # consecutive equal-size reads before a file is "done"
STABLE_INTERVAL = 1.0    # seconds between size checks
RETRY_BACKOFF = [5, 15, 30, 60, 120]  # seconds


# --------------------------- config + state ---------------------------

def load_config() -> dict:
    p = argparse.ArgumentParser(description="WedFind desktop ingest agent")
    p.add_argument("--config")
    p.add_argument("--api-url")
    p.add_argument("--api-key")
    p.add_argument("--event-id", type=int)
    p.add_argument("--folder")
    p.add_argument("--poll-seconds", type=int, default=10)
    a = p.parse_args()

    cfg = {}
    if a.config:
        with open(a.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    # CLI overrides file
    if a.api_url:
        cfg["api_url"] = a.api_url
    if a.api_key:
        cfg["api_key"] = a.api_key
    if a.event_id is not None:
        cfg["event_id"] = a.event_id
    if a.folder:
        cfg["folder"] = a.folder
    cfg.setdefault("poll_seconds", a.poll_seconds)

    missing = [k for k in ("api_url", "api_key", "event_id", "folder") if not cfg.get(k)]
    if missing:
        log.error("Missing config: %s", ", ".join(missing))
        sys.exit(1)
    cfg["api_url"] = cfg["api_url"].rstrip("/")
    if not os.path.isdir(cfg["folder"]):
        log.error("Folder does not exist: %s", cfg["folder"])
        sys.exit(1)
    return cfg


def _state_path(cfg: dict) -> str:
    key = f"{cfg['api_url']}|{cfg['event_id']}|{cfg['folder']}"
    h = hashlib.sha256(key.encode()).hexdigest()[:12]
    base = os.path.join(os.path.expanduser("~"), ".wedfind_agent")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"state_{h}.json")


def load_state(cfg: dict) -> set:
    path = _state_path(cfg)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return set(json.load(f).get("synced", []))
        except Exception:
            log.warning("Could not read state file; starting fresh")
    return set()


def save_state(cfg: dict, synced: set) -> None:
    path = _state_path(cfg)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"synced": sorted(synced)}, f)
    os.replace(tmp, path)


# --------------------------- helpers ---------------------------

def file_key(path: str) -> str:
    """Stable identity: sha256 of content (so renames don't re-upload)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in ALLOWED_EXT


def wait_until_stable(path: str) -> bool:
    """Wait until file size stops changing (still being copied)."""
    last = -1
    stable = 0
    for _ in range(60):  # up to ~60s
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size == last and size > 0:
            stable += 1
            if stable >= STABLE_CHECKS:
                return True
        else:
            stable = 0
            last = size
        time.sleep(STABLE_INTERVAL)
    return False


# --------------------------- uploader ---------------------------

class Uploader:
    def __init__(self, cfg: dict, synced: set):
        self.cfg = cfg
        self.synced = synced
        self.q: "queue.Queue[str]" = queue.Queue()
        self.lock = threading.Lock()
        self.count = 0
        self.url = f"{cfg['api_url']}/photos/upload/{cfg['event_id']}"
        self.headers = {"X-API-Key": cfg["api_key"]}

    def enqueue(self, path: str):
        self.q.put(path)

    def _upload(self, path: str) -> bool:
        fname = os.path.basename(path)
        try:
            with open(path, "rb") as f:
                resp = requests.post(
                    self.url, headers=self.headers,
                    files={"files": (fname, f, "application/octet-stream")},
                    timeout=120,
                )
        except Exception as e:
            log.warning("Upload error %s: %s", fname, e)
            return False
        if resp.status_code in (200, 201):
            return True
        if resp.status_code in (401, 403):
            log.error("Auth failed (%s) — check API key. Stopping uploads.", resp.status_code)
            raise SystemExit(1)
        log.warning("Upload failed %s: HTTP %s %s", fname, resp.status_code, resp.text[:200])
        return False

    def worker(self):
        while True:
            path = self.q.get()
            if path is None:
                return
            try:
                if not os.path.exists(path) or not is_image(path):
                    continue
                if not wait_until_stable(path):
                    log.warning("File never stabilized, skipping: %s", path)
                    continue
                key = file_key(path)
                with self.lock:
                    if key in self.synced:
                        continue
                ok = False
                for delay in [0] + RETRY_BACKOFF:
                    if delay:
                        time.sleep(delay)
                    if self._upload(path):
                        ok = True
                        break
                    log.info("Retrying %s in backoff…", os.path.basename(path))
                if ok:
                    with self.lock:
                        self.synced.add(key)
                        self.count += 1
                        save_state(self.cfg, self.synced)
                    log.info("Synced (%d): %s", self.count, os.path.basename(path))
                else:
                    log.error("Giving up on %s after retries; will retry next scan", os.path.basename(path))
            finally:
                self.q.task_done()


class Handler(FileSystemEventHandler):
    def __init__(self, up: Uploader):
        self.up = up

    def on_created(self, event):
        if not event.is_directory and is_image(event.src_path):
            self.up.enqueue(event.src_path)

    def on_moved(self, event):
        if not event.is_directory and is_image(event.dest_path):
            self.up.enqueue(event.dest_path)


def initial_scan(cfg: dict, up: Uploader):
    folder = cfg["folder"]
    for root, _dirs, files in os.walk(folder):
        for name in files:
            p = os.path.join(root, name)
            if is_image(p):
                up.enqueue(p)


def main():
    cfg = load_config()
    synced = load_state(cfg)
    log.info("WedFind agent starting — folder=%s event=%s (%d already synced)",
             cfg["folder"], cfg["event_id"], len(synced))

    up = Uploader(cfg, synced)
    t = threading.Thread(target=up.worker, daemon=True)
    t.start()

    initial_scan(cfg, up)

    observer = Observer()
    observer.schedule(Handler(up), cfg["folder"], recursive=True)
    observer.start()
    log.info("Watching for new photos. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(cfg["poll_seconds"])
    except KeyboardInterrupt:
        log.info("Stopping…")
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
