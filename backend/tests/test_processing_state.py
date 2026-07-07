"""SSE processing-state store: memory fallback + Redis backend contract."""
import time

import pytest

from app.services import processing_state as ps


def test_memory_store_put_get_pop():
    store = ps.MemoryStateStore(ttl_seconds=60)
    store.put("rid-1", {"status": "starting"})
    assert store.get("rid-1") == {"status": "starting"}
    store.pop("rid-1")
    assert store.get("rid-1") is None


def test_memory_store_ttl_eviction():
    store = ps.MemoryStateStore(ttl_seconds=0.05)
    store.put("rid-old", {"status": "starting"})
    time.sleep(0.1)
    # Any write lazily evicts expired entries; reads honor expiry too.
    store.put("rid-new", {"status": "starting"})
    assert store.get("rid-old") is None
    assert store.get("rid-new") is not None


def test_get_store_falls_back_to_memory_without_redis(monkeypatch):
    """With an unreachable REDIS_URL the singleton must degrade to memory."""
    monkeypatch.setattr(ps, "_store", None)  # reset singleton
    monkeypatch.setattr(ps.settings, "REDIS_URL", "redis://127.0.0.1:1/0")
    store = ps.get_store()
    assert isinstance(store, ps.MemoryStateStore)
    monkeypatch.setattr(ps, "_store", None)  # leave clean for other tests


def test_redis_store_roundtrip_if_available():
    try:
        import redis
        client = redis.Redis.from_url("redis://localhost:6379/0", socket_connect_timeout=0.5)
        client.ping()
    except Exception:
        pytest.skip("no local Redis")

    store = ps.RedisStateStore("redis://localhost:6379/0", ttl_seconds=60)
    store.put("rid-r", {"status": "matching", "progress": 70})
    assert store.get("rid-r") == {"status": "matching", "progress": 70}
    store.pop("rid-r")
    assert store.get("rid-r") is None
