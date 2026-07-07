"""SSE processing-state store.

Selfie processing publishes progress frames keyed by the guest's request_id;
the SSE stream endpoint polls them. Redis-backed when reachable so state
survives multiple web replicas (Fargate/gunicorn -w N); falls back to an
in-process TTL dict for dev and tests without Redis.
"""
import json
import logging
import time
from typing import Optional, Protocol

from ..config import settings

logger = logging.getLogger("wedfind.sse_state")

STATE_TTL_SECONDS = 600  # abandoned entries die; completed ones are popped


class StateStore(Protocol):
    def put(self, request_id: str, state: dict) -> None: ...
    def get(self, request_id: str) -> Optional[dict]: ...
    def pop(self, request_id: str) -> None: ...


class MemoryStateStore:
    """Process-local fallback. Single-instance only."""

    def __init__(self, ttl_seconds: float = STATE_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[dict, float]] = {}

    def _evict(self) -> None:
        now = time.monotonic()
        for key in [k for k, (_, ts) in self._data.items() if now - ts > self._ttl]:
            self._data.pop(key, None)

    def put(self, request_id: str, state: dict) -> None:
        self._evict()
        self._data[request_id] = (state, time.monotonic())

    def get(self, request_id: str) -> Optional[dict]:
        item = self._data.get(request_id)
        if not item:
            return None
        state, ts = item
        if time.monotonic() - ts > self._ttl:
            self._data.pop(request_id, None)
            return None
        return state

    def pop(self, request_id: str) -> None:
        self._data.pop(request_id, None)


class RedisStateStore:
    """Shared store — safe across web replicas. TTL enforced by Redis."""

    def __init__(self, url: str, ttl_seconds: int = STATE_TTL_SECONDS):
        import redis

        self._ttl = int(ttl_seconds)
        self._client = redis.Redis.from_url(
            url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True
        )
        self._client.ping()  # fail fast so get_store() can fall back

    @staticmethod
    def _key(request_id: str) -> str:
        return f"sse_state:{request_id}"

    def put(self, request_id: str, state: dict) -> None:
        self._client.setex(self._key(request_id), self._ttl, json.dumps(state))

    def get(self, request_id: str) -> Optional[dict]:
        raw = self._client.get(self._key(request_id))
        return json.loads(raw) if raw else None

    def pop(self, request_id: str) -> None:
        self._client.delete(self._key(request_id))


_store: Optional[StateStore] = None


def get_store() -> StateStore:
    """Singleton: Redis when reachable, else in-process memory (dev/test)."""
    global _store
    if _store is None:
        try:
            _store = RedisStateStore(settings.REDIS_URL)
            logger.info("SSE state store: redis")
        except Exception:
            _store = MemoryStateStore()
            logger.warning(
                "SSE state store: Redis unreachable — using in-process memory "
                "(single instance only; fine for dev/test)"
            )
    return _store
