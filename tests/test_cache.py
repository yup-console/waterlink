from __future__ import annotations

import time

from waterlink.cache import TTLCache


def test_set_and_get():
    cache: TTLCache[str, int] = TTLCache(max_size=10, ttl_seconds=60)
    cache.set("a", 1)
    assert cache.get("a") == 1
    assert "a" in cache


def test_expiry():
    cache: TTLCache[str, int] = TTLCache(max_size=10, ttl_seconds=0.01)
    cache.set("a", 1)
    time.sleep(0.02)
    assert cache.get("a") is None
    assert "a" not in cache


def test_lru_eviction():
    cache: TTLCache[str, int] = TTLCache(max_size=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)  # evicts "a"
    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_get_refreshes_lru_order():
    cache: TTLCache[str, int] = TTLCache(max_size=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # touch "a" so "b" becomes least-recently-used
    cache.set("c", 3)  # evicts "b"
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3


def test_invalidate_and_clear():
    cache: TTLCache[str, int] = TTLCache()
    cache.set("a", 1)
    cache.invalidate("a")
    assert cache.get("a") is None

    cache.set("b", 2)
    cache.clear()
    assert len(cache) == 0
